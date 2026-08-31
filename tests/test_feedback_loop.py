"""
反馈闭环自动化测试 (Task 12)

覆盖闭环链路:
1. 对话保存 -> 用户评分 -> 高分(>=4)进入知识库 / 低分(<4)标记待反馈 -> 闭环统计聚合
2. 流式TTS分句合成: process_stream 逐句推送 audio 事件 (每句一个, 按序到达)
3. 闭环建议收件箱: auto建议进入收件箱 -> 人工确认写RAG(trust=1.0)/驳回不写 -> 闭环统计聚合
"""

import asyncio
import base64
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from tests.mock_services import create_minimal_wav_bytes


# ---------------------------------------------------------------------------
# 流式TTS分句合成测试: 轻量级 VoiceChatController 构造 (不加载真实 LLM/RAG/TTS)
# ---------------------------------------------------------------------------

def make_stream_controller(chunks, tts_audio=None, api_mode=True, character_id="march7th"):
    """构造跳过 __init__ 的 VoiceChatController, mock 掉重资源依赖。

    Returns:
        (controller, synthesized_texts): synthesized_texts 记录 TTS 收到的每句文本
    """
    from voice_chat import VoiceChatController

    controller = VoiceChatController.__new__(VoiceChatController)

    controller.current_character = None
    controller.current_character_id = character_id
    controller.persona_manager = None
    controller.llm_active = True
    controller.tts_active = False
    controller._last_dialogue_id = None
    controller._tts_lock = threading.Lock()

    controller.llm = MagicMock()
    controller.llm.model_name = "mock-model"
    controller.llm.generate_stream = MagicMock(return_value=iter(chunks))
    controller.llm._last_debug_info = {}

    controller.tts = MagicMock()
    if tts_audio is None:
        tts_audio = create_minimal_wav_bytes()
    synthesized_texts = []

    def fake_synthesize(text, *args, **kwargs):
        synthesized_texts.append(text)
        return tts_audio

    controller.tts.synthesize = MagicMock(side_effect=fake_synthesize)

    controller.emotion_classifier = MagicMock()
    controller.emotion_classifier.predict = MagicMock(return_value="neutral")

    controller.is_api_mode = MagicMock(return_value=api_mode)
    controller._ensure_llm_active = MagicMock(return_value=True)
    controller._release_llm = MagicMock(return_value=True)
    controller._ensure_tts_active = MagicMock(return_value=True)
    controller._release_tts = MagicMock(return_value=True)
    controller._save_to_history = MagicMock(return_value=123)

    return controller, synthesized_texts


async def collect_stream_events(controller, **kwargs):
    events = []
    async for event in controller.process_stream("你好", **kwargs):
        events.append(event)
    return events


def split_events(events):
    return {
        "text": [e for e in events if e["type"] == "text"],
        "audio": [e for e in events if e["type"] == "audio"],
        "done": [e for e in events if e["type"] == "done"],
        "error": [e for e in events if e["type"] == "error"],
    }


class TestStreamSentenceTTS:
    """流式TTS分句合成测试"""

    async def test_audio_event_per_sentence(self):
        """每个完整句子产生一个独立的 audio 事件, 且与TTS调用一一对应"""
        chunks = ["你好呀！本姑娘", "是三月七。今天也要", "加油哦！一起去冒险", "吧。"]
        controller, synthesized = make_stream_controller(chunks)
        events = await collect_stream_events(controller)
        parts = split_events(events)

        expected_sentences = ["你好呀！", "本姑娘是三月七。", "今天也要加油哦！", "一起去冒险吧。"]

        assert parts["error"] == []
        assert len(parts["done"]) == 1
        # 每句一个 audio 事件
        assert len(parts["audio"]) == 4
        assert [e["text"] for e in parts["audio"]] == expected_sentences
        # TTS 按句合成, 顺序一致
        assert synthesized == expected_sentences
        # 文本流覆盖全部内容
        assert ''.join(e["content"] for e in parts["text"]) == ''.join(expected_sentences)
        # 音频为有效 WAV
        for e in parts["audio"]:
            assert base64.b64decode(e["audio"]).startswith(b"RIFF")

    async def test_audio_events_arrive_before_done(self):
        """分句音频事件必须在 done 事件之前推送"""
        chunks = ["第一句话！第二句话！第三句话！"]
        controller, _ = make_stream_controller(chunks)
        events = await collect_stream_events(controller)

        audio_indexes = [i for i, e in enumerate(events) if e["type"] == "audio"]
        done_index = next(i for i, e in enumerate(events) if e["type"] == "done")
        assert audio_indexes
        assert max(audio_indexes) < done_index

    async def test_trailing_text_without_punctuation_is_synthesized(self):
        """结尾无标点的文本也应作为尾句合成"""
        chunks = ["你好呀！还有一句没有标点结尾"]
        controller, synthesized = make_stream_controller(chunks)
        events = await collect_stream_events(controller)
        parts = split_events(events)

        assert len(parts["audio"]) == 2
        assert parts["audio"][0]["text"] == "你好呀！"
        assert parts["audio"][1]["text"] == "还有一句没有标点结尾"


class TestStreamSentenceTTSEdgeCases:
    """流式TTS分句合成边界场景"""

    async def test_emotion_tag_not_synthesized(self):
        """纯情绪标签不入队合成, 但保留在完整响应中用于历史保存"""
        chunks = ["你好呀！[EMOTION: happy]"]
        controller, synthesized = make_stream_controller(chunks)
        events = await collect_stream_events(controller)
        parts = split_events(events)

        # 只有 "你好呀！" 被合成
        assert len(parts["audio"]) == 1
        assert parts["audio"][0]["text"] == "你好呀！"
        assert synthesized == ["你好呀！"]

        # 完整响应(含情绪标签)保存进历史, 且提取出情绪
        controller._save_to_history.assert_called_once()
        call = controller._save_to_history.call_args
        assert call.args[1] == "你好呀！[EMOTION: happy]"
        assert call.kwargs.get("emotion") == "happy"
        # 已有情绪标签时不再调用情绪分类器
        controller.emotion_classifier.predict.assert_not_called()

    async def test_tts_failure_still_completes_stream(self):
        """TTS合成失败(空音频)时仍完成事件流: text + done, 无 audio"""
        chunks = ["第一句。第二句。"]
        controller, synthesized = make_stream_controller(chunks, tts_audio=b"")
        events = await collect_stream_events(controller)
        parts = split_events(events)

        assert parts["audio"] == []
        assert parts["error"] == []
        assert len(parts["text"]) == 2
        assert len(parts["done"]) == 1

    async def test_llm_error_yields_error_event(self):
        """LLM流式错误时推送 error 事件且不产生音频"""
        chunks = ["[ERROR] 模型加载失败"]
        controller, synthesized = make_stream_controller(chunks)
        events = await collect_stream_events(controller)
        parts = split_events(events)

        assert len(parts["error"]) == 1
        assert "模型加载失败" in parts["error"][0]["error"]
        assert parts["audio"] == []
        assert parts["done"] == []
        assert synthesized == []

    async def test_local_mode_waits_for_llm_completion(self):
        """本地(非API)模式下TTS等待LLM完成后再合成, 流程不阻塞不丢句"""
        chunks = ["你好呀！", "本姑娘是三月七。", "一起去冒险吧。"]
        controller, synthesized = make_stream_controller(chunks, api_mode=False)
        events = await collect_stream_events(controller)
        parts = split_events(events)

        assert parts["error"] == []
        assert len(parts["audio"]) == 3
        assert [e["text"] for e in parts["audio"]] == ["你好呀！", "本姑娘是三月七。", "一起去冒险吧。"]

    async def test_done_event_contains_sentence_stats(self):
        """done 事件包含分句合成统计(闭环观测)"""
        chunks = ["你好呀！", "一起去冒险吧。"]
        controller, _ = make_stream_controller(chunks)
        events = await collect_stream_events(controller)
        done = split_events(events)["done"][0]

        assert done["conversation_id"] == 123
        assert done["tts_sentences"]["total"] == 2
        assert done["tts_sentences"]["synthesized"] == 2


# ---------------------------------------------------------------------------
# 反馈闭环 API 测试: 对话 -> 评分 -> 入库/待反馈 -> 统计
# ---------------------------------------------------------------------------

@pytest.fixture
def loop_db(test_db):
    """Mock database 与 persona_manager, 记录闭环关键动作"""
    import database
    import persona_manager

    calls = {"set_needs_feedback": [], "save_dialogue": []}

    original_functions = {
        "get_db": database.get_db,
        "save_conversation": getattr(database, "save_conversation", None),
        "get_conversation_by_id": getattr(database, "get_conversation_by_id", None),
        "get_conversations_by_role": getattr(database, "get_conversations_by_role", None),
        "update_rating": getattr(database, "update_rating", None),
        "set_needs_feedback": getattr(database, "set_needs_feedback", None),
        "get_preference_stats": getattr(database, "get_preference_stats", None),
        "get_total_conversation_count": getattr(database, "get_total_conversation_count", None),
    }
    original_persona = persona_manager.get_persona_manager

    def mock_get_db():
        return test_db

    def mock_save_conversation(db, user_id, character, user_input, bot_reply,
                               session_id=None, emotion=None):
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (user_id, character, user_input, bot_reply) VALUES (?, ?, ?, ?)",
                (user_id, character, user_input, bot_reply),
            )
            return cursor.lastrowid

    def mock_get_conversation_by_id(db, conversation_id):
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def mock_get_conversations_by_role(db, role=None, limit=100):
        with db.get_cursor() as cursor:
            if role and role != "all":
                cursor.execute(
                    """SELECT c.*, u.username, u.role FROM conversations c
                       JOIN users u ON c.user_id = u.id
                       WHERE u.role = ? ORDER BY c.timestamp DESC LIMIT ?""",
                    (role, limit),
                )
            else:
                cursor.execute(
                    """SELECT c.*, u.username, u.role FROM conversations c
                       JOIN users u ON c.user_id = u.id
                       ORDER BY c.timestamp DESC LIMIT ?""",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def mock_update_rating(db, conversation_id, rating):
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE conversations SET rating = ? WHERE id = ?",
                (rating, conversation_id),
            )
            return cursor.rowcount > 0

    def mock_set_needs_feedback(db, conversation_id, needs_feedback):
        calls["set_needs_feedback"].append((conversation_id, needs_feedback))
        return True

    def mock_get_preference_stats(db, user_id, days=30):
        # rating_distribution 键为 int, 与 database.get_rating_distribution 一致
        return {
            "top_positive_keywords": [],
            "top_negative_keywords": [],
            "interest_keywords": [],
            "rating_distribution": {4: 2, 5: 3},
            "conversation_trend": [],
        }

    def mock_get_total_conversation_count(db, user_id):
        return 10

    database.get_db = mock_get_db
    database.save_conversation = mock_save_conversation
    database.get_conversation_by_id = mock_get_conversation_by_id
    database.get_conversations_by_role = mock_get_conversations_by_role
    database.update_rating = mock_update_rating
    database.set_needs_feedback = mock_set_needs_feedback
    database.get_preference_stats = mock_get_preference_stats
    database.get_total_conversation_count = mock_get_total_conversation_count

    mock_persona = MagicMock()
    mock_persona.save_dialogue = MagicMock(
        side_effect=lambda **kwargs: calls["save_dialogue"].append(kwargs) or "record_id"
    )
    persona_manager.get_persona_manager = MagicMock(return_value=mock_persona)

    yield {"db": test_db, "calls": calls}

    for name, func in original_functions.items():
        if func is not None:
            setattr(database, name, func)
    persona_manager.get_persona_manager = original_persona


class TestFeedbackLoopClosedLoop:
    """反馈闭环: 对话 -> 评分 -> 高分入库/低分待反馈"""

    async def test_high_rating_adds_to_knowledge_base(
        self, client: AsyncClient, auth_headers: dict, loop_db: dict, test_user: dict
    ):
        """评分>=4: 对话进入persona知识库, 评分落库, 不标记待反馈"""
        import database

        conv_id = database.save_conversation(
            loop_db["db"], test_user["id"], "march7th",
            "讲个笑话", "好呀，本姑娘给你讲一个！",
        )

        response = await client.post(
            "/api/chat/rating",
            json={"conversation_id": conv_id, "rating": 5},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["needs_feedback"] is False
        assert "知识库" in data["message"]

        # 高分对话进入persona知识库(闭环生效)
        assert len(loop_db["calls"]["save_dialogue"]) == 1
        assert loop_db["calls"]["save_dialogue"][0]["rating"] == 5
        assert loop_db["calls"]["save_dialogue"][0]["user_input"] == "讲个笑话"

        # 评分已写入数据库
        conv = database.get_conversation_by_id(loop_db["db"], conv_id)
        assert conv["rating"] == 5
        # 高分不需要补充反馈
        assert loop_db["calls"]["set_needs_feedback"] == []

    async def test_low_rating_marks_needs_feedback(
        self, client: AsyncClient, auth_headers: dict, loop_db: dict, test_user: dict
    ):
        """评分<4: 标记待反馈, 不进入知识库, 评分落库"""
        import database

        conv_id = database.save_conversation(
            loop_db["db"], test_user["id"], "march7th",
            "介绍一下你自己", "本姑娘是三月七！",
        )

        response = await client.post(
            "/api/chat/rating",
            json={"conversation_id": conv_id, "rating": 2},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["needs_feedback"] is True

        # 低分触发待反馈标记(闭环的反馈收集入口)
        assert (conv_id, True) in loop_db["calls"]["set_needs_feedback"]
        # 低分不进入知识库
        assert loop_db["calls"]["save_dialogue"] == []

        conv = database.get_conversation_by_id(loop_db["db"], conv_id)
        assert conv["rating"] == 2

    async def test_rating_updates_existing_conversation(
        self, client: AsyncClient, auth_headers: dict, loop_db: dict, test_user: dict
    ):
        """同一对话的评分可以被更新(最新评分生效)"""
        import database

        conv_id = database.save_conversation(
            loop_db["db"], test_user["id"], "march7th", "你好", "你好呀！",
        )

        await client.post(
            "/api/chat/rating", json={"conversation_id": conv_id, "rating": 3},
            headers=auth_headers,
        )
        response = await client.post(
            "/api/chat/rating", json={"conversation_id": conv_id, "rating": 4},
            headers=auth_headers,
        )

        assert response.status_code == 200
        conv = database.get_conversation_by_id(loop_db["db"], conv_id)
        assert conv["rating"] == 4
        # 最终评分为高分 -> 进入知识库
        assert len(loop_db["calls"]["save_dialogue"]) == 1


class TestFeedbackLoopStats:
    """闭环统计聚合: 评分分布 -> 偏好统计 -> Admin闭环卡片数据源"""

    async def test_preference_stats_loop_aggregation(
        self, client: AsyncClient, auth_headers: dict, loop_db: dict, test_user: dict
    ):
        """/api/user/preference/stats 正确聚合评分闭环统计"""
        response = await client.get(
            "/api/user/preference/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        summary = data["stats"]["summary"]
        # rating_distribution {"4": 2, "5": 3} -> 5条已评分, 平均 4.6
        assert summary["total_conversations"] == 10
        assert summary["total_rated_conversations"] == 5
        assert summary["avg_rating"] == 4.6
        assert data["stats"]["rating_distribution"] == {"4": 2, "5": 3}

    async def test_admin_conversations_provide_rating_for_loop_cards(
        self, client: AsyncClient, admin_auth_headers: dict, loop_db: dict, test_user: dict
    ):
        """Admin对话列表返回rating字段(闭环统计卡片数据源), 支持筛选已评分/待评分"""
        import database

        conv_rated = database.save_conversation(
            loop_db["db"], test_user["id"], "march7th", "已评分的对话", "回复1")
        conv_unrated = database.save_conversation(
            loop_db["db"], test_user["id"], "march7th", "未评分的对话", "回复2")
        database.update_rating(loop_db["db"], conv_rated, 5)

        response = await client.get(
            "/api/admin/conversations", headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        ratings = {c["id"]: c["rating"] for c in data["conversations"]}
        assert ratings[conv_rated] == 5
        assert ratings[conv_unrated] is None


# ---------------------------------------------------------------------------
# 闭环建议收件箱测试: auto建议 -> 人工确认(写RAG)/驳回(不写) -> 统计聚合
# ---------------------------------------------------------------------------

SUGGESTION_PAYLOAD = {
    "is_consistent": False,
    "deviation": "回复语气过于正式，缺少三月七的俏皮感",
    "suggestion": "三月七的语气应更活泼俏皮，多用第一人称「本姑娘」",
    "confidence": 0.72,
}


def _make_auth_headers(user_id: int, username: str, role: str = "user") -> dict:
    """为指定用户构造 JWT 认证头（与 conftest 保持一致）。"""
    import jwt
    from personal_config import JWT_CONFIG

    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    token = jwt.encode(
        payload, JWT_CONFIG.get("secret", "march7th_secret_key_2024"), algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def suggestion_db(test_db):
    """闭环建议收件箱环境: feedback_details 表 + database/persona_manager mock。

    记录闭环关键动作: calls["add_knowledge_entry"] 确认写RAG,
    calls["collection_update"] 弱权重条目升级。
    """
    import json

    import database
    import persona_manager

    with test_db.get_cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                user_id INTEGER NOT NULL,
                feedback_type TEXT,
                context_snapshot TEXT,
                correction_suggestion TEXT,
                model_name TEXT,
                confirmed INTEGER DEFAULT 0,
                origin TEXT DEFAULT 'user',
                confidence REAL DEFAULT 1.0,
                suggestion_status TEXT DEFAULT 'pending',
                rag_updated INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    calls = {"add_knowledge_entry": [], "collection_update": []}

    original_functions = {
        "get_db": database.get_db,
        "save_conversation": getattr(database, "save_conversation", None),
        "get_conversation_by_id": getattr(database, "get_conversation_by_id", None),
        "save_feedback_detail": getattr(database, "save_feedback_detail", None),
        "get_feedback_detail_by_id": getattr(database, "get_feedback_detail_by_id", None),
        "confirm_feedback_detail": getattr(database, "confirm_feedback_detail", None),
        "reject_feedback_detail": getattr(database, "reject_feedback_detail", None),
        "update_feedback_rag_status": getattr(database, "update_feedback_rag_status", None),
        "get_pending_suggestions": getattr(database, "get_pending_suggestions", None),
        "get_pending_suggestions_by_conversation": getattr(
            database, "get_pending_suggestions_by_conversation", None),
        "get_feedback_loop_stats": getattr(database, "get_feedback_loop_stats", None),
    }
    original_persona = persona_manager.get_persona_manager

    def _parse_row(row):
        detail = dict(row)
        created_at = detail.get('created_at')
        if isinstance(created_at, str):
            try:
                detail['created_at'] = datetime.strptime(
                    created_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                detail['created_at'] = None
        return detail

    def mock_get_db():
        return test_db

    def mock_save_conversation(db, user_id, character, user_input, bot_reply,
                               session_id=None, emotion=None):
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (user_id, character, user_input, bot_reply) VALUES (?, ?, ?, ?)",
                (user_id, character, user_input, bot_reply),
            )
            return cursor.lastrowid

    def mock_get_conversation_by_id(db, conversation_id):
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def mock_save_feedback_detail(db, conversation_id, user_id, feedback_type,
                                  context_snapshot=None, correction_suggestion=None,
                                  model_name=None, confirmed=False, origin='user',
                                  confidence=1.0, suggestion_status='pending'):
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO feedback_details
                   (conversation_id, user_id, feedback_type, context_snapshot, correction_suggestion,
                    model_name, confirmed, origin, confidence, suggestion_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (conversation_id, user_id, feedback_type,
                 json.dumps(context_snapshot, ensure_ascii=False) if context_snapshot else None,
                 correction_suggestion, model_name, 1 if confirmed else 0,
                 origin if origin in ('user', 'auto') else 'user',
                 max(0.0, min(1.0, float(confidence))) if confidence is not None else 1.0,
                 suggestion_status if suggestion_status in ('pending', 'confirmed', 'rejected') else 'pending'),
            )
            return cursor.lastrowid

    def mock_get_feedback_detail_by_id(db, feedback_detail_id):
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM feedback_details WHERE id = ?", (feedback_detail_id,))
            row = cursor.fetchone()
            return _parse_row(row) if row else None

    def mock_confirm_feedback_detail(db, feedback_detail_id, user_id=None):
        with db.get_cursor() as cursor:
            if user_id is not None:
                cursor.execute(
                    "UPDATE feedback_details SET confirmed = 1, suggestion_status = 'confirmed'"
                    " WHERE id = ? AND user_id = ?",
                    (feedback_detail_id, user_id))
            else:
                cursor.execute(
                    "UPDATE feedback_details SET confirmed = 1, suggestion_status = 'confirmed'"
                    " WHERE id = ?",
                    (feedback_detail_id,))
            return cursor.rowcount > 0

    def mock_reject_feedback_detail(db, feedback_detail_id, user_id=None):
        with db.get_cursor() as cursor:
            if user_id is not None:
                cursor.execute(
                    "UPDATE feedback_details SET suggestion_status = 'rejected'"
                    " WHERE id = ? AND user_id = ?",
                    (feedback_detail_id, user_id))
            else:
                cursor.execute(
                    "UPDATE feedback_details SET suggestion_status = 'rejected'"
                    " WHERE id = ?",
                    (feedback_detail_id,))
            return cursor.rowcount > 0

    def mock_update_feedback_rag_status(db, feedback_detail_id, rag_updated=True):
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE feedback_details SET rag_updated = ? WHERE id = ?",
                (1 if rag_updated else 0, feedback_detail_id))
            return cursor.rowcount > 0

    def mock_get_pending_suggestions(db, user_id=None, origin='auto', limit=50):
        with db.get_cursor() as cursor:
            query = """SELECT fd.*, c.user_input AS conv_user_input, c.bot_reply AS conv_bot_reply,
                              c.character AS conv_character, c.id AS conv_id
                       FROM feedback_details fd
                       LEFT JOIN conversations c ON fd.conversation_id = c.id
                       WHERE fd.suggestion_status = 'pending'"""
            params = []
            if user_id is not None:
                query += " AND fd.user_id = ?"
                params.append(user_id)
            if origin is not None:
                query += " AND fd.origin = ?"
                params.append(origin)
            query += " ORDER BY fd.created_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [_parse_row(r) for r in cursor.fetchall()]

    def mock_get_pending_suggestions_by_conversation(db, conversation_id, user_id=None):
        with db.get_cursor() as cursor:
            query = """SELECT fd.*, c.user_input AS conv_user_input, c.bot_reply AS conv_bot_reply,
                              c.character AS conv_character
                       FROM feedback_details fd
                       LEFT JOIN conversations c ON fd.conversation_id = c.id
                       WHERE fd.conversation_id = ? AND fd.suggestion_status = 'pending'"""
            params = [conversation_id]
            if user_id is not None:
                query += " AND fd.user_id = ?"
                params.append(user_id)
            query += " ORDER BY fd.created_at DESC"
            cursor.execute(query, params)
            return [_parse_row(r) for r in cursor.fetchall()]

    def mock_get_feedback_loop_stats(db, user_id=None):
        with db.get_cursor() as cursor:
            user_filter = ""
            params = []
            if user_id is not None:
                user_filter = " AND user_id = ?"
                params.append(user_id)

            def _count(extra):
                cursor.execute(
                    f"SELECT COUNT(*) AS cnt FROM feedback_details WHERE 1=1{user_filter}{extra}",
                    params)
                return cursor.fetchone()['cnt']

            auto_total = _count(" AND origin = 'auto'")
            auto_confirmed = _count(
                " AND origin = 'auto' AND suggestion_status = 'confirmed'")
            auto_rejected = _count(
                " AND origin = 'auto' AND suggestion_status = 'rejected'")
            pending_total = _count(" AND suggestion_status = 'pending'")
            rag_updated_total = _count(" AND rag_updated = 1")

            decided = auto_confirmed + auto_rejected
            confirm_rate = round(auto_confirmed / decided, 4) if decided > 0 else None
            return {
                "auto_generated": auto_total,
                "auto_confirmed": auto_confirmed,
                "auto_rejected": auto_rejected,
                "auto_pending": auto_total - auto_confirmed - auto_rejected,
                "pending_total": pending_total,
                "confirm_rate": confirm_rate,
                "rag_updated_total": rag_updated_total,
            }

    database.get_db = mock_get_db
    database.save_conversation = mock_save_conversation
    database.get_conversation_by_id = mock_get_conversation_by_id
    database.save_feedback_detail = mock_save_feedback_detail
    database.get_feedback_detail_by_id = mock_get_feedback_detail_by_id
    database.confirm_feedback_detail = mock_confirm_feedback_detail
    database.reject_feedback_detail = mock_reject_feedback_detail
    database.update_feedback_rag_status = mock_update_feedback_rag_status
    database.get_pending_suggestions = mock_get_pending_suggestions
    database.get_pending_suggestions_by_conversation = mock_get_pending_suggestions_by_conversation
    database.get_feedback_loop_stats = mock_get_feedback_loop_stats

    # persona_manager mock: 记录确认写RAG/弱权重条目升级动作, 不触碰真实 ChromaDB
    mock_collection = MagicMock()
    mock_collection.get = MagicMock(return_value={"ids": [], "metadatas": []})

    def fake_collection_update(**kwargs):
        calls["collection_update"].append(kwargs)

    mock_collection.update = MagicMock(side_effect=fake_collection_update)

    mock_persona = MagicMock()

    def fake_add_knowledge_entry(content, metadata=None):
        calls["add_knowledge_entry"].append(
            {"content": content, "metadata": metadata})
        return f"entry_{len(calls['add_knowledge_entry'])}"

    mock_persona.add_knowledge_entry = MagicMock(side_effect=fake_add_knowledge_entry)
    mock_persona.load_persona_db = MagicMock(return_value=mock_collection)
    persona_manager.get_persona_manager = MagicMock(return_value=mock_persona)

    # 第二个普通用户（跨用户权限测试用）
    from tests.conftest import create_test_user
    other_user_id = create_test_user(test_db, "otheruser", "otherpassword123", "user")

    def save_suggestion(conversation_id, user_id, origin='auto', confidence=0.72,
                        status='pending', rag_updated=False,
                        correction_suggestion=None, context_snapshot=None,
                        feedback_type='persona_consistency'):
        detail_id = mock_save_feedback_detail(
            test_db, conversation_id, user_id, feedback_type,
            context_snapshot=context_snapshot,
            correction_suggestion=correction_suggestion or json.dumps(
                SUGGESTION_PAYLOAD, ensure_ascii=False),
            model_name='march7th',
            origin=origin,
            confidence=confidence,
            suggestion_status=status,
        )
        if rag_updated:
            with test_db.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE feedback_details SET rag_updated = 1 WHERE id = ?",
                    (detail_id,))
        return detail_id

    yield {
        "db": test_db,
        "calls": calls,
        "collection": mock_collection,
        "other_user": {"id": other_user_id, "username": "otheruser", "role": "user"},
        "other_headers": _make_auth_headers(other_user_id, "otheruser"),
        "save_suggestion": save_suggestion,
    }

    for name, func in original_functions.items():
        if func is not None:
            setattr(database, name, func)
    persona_manager.get_persona_manager = original_persona


class TestSuggestionInbox:
    """闭环建议收件箱: auto建议进入收件箱等待人工确认，永不直接写RAG"""

    async def test_pending_lists_only_auto_pending_suggestions(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """收件箱只返回本人 origin=auto 且 pending 的建议"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")

        save = suggestion_db["save_suggestion"]
        pending_id = save(conv_id, test_user["id"], origin='auto')
        save(conv_id, test_user["id"], origin='auto', status='confirmed')
        save(conv_id, test_user["id"], origin='user')
        save(conv_id, suggestion_db["other_user"]["id"], origin='auto')

        response = await client.get(
            "/api/rag/suggestions/pending", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 1
        assert [s["id"] for s in data["suggestions"]] == [pending_id]
        assert data["suggestions"][0]["origin"] == "auto"
        assert data["suggestions"][0]["suggestion_status"] == "pending"

    async def test_pending_item_fields_formatted(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """收件箱条目格式化: confidence分级/suggestion JSON解析/对话内容回填"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "介绍一下你自己", "我是一个AI助手。")

        save = suggestion_db["save_suggestion"]
        medium_id = save(conv_id, test_user["id"], confidence=0.72)
        high_id = save(conv_id, test_user["id"], confidence=0.9)
        low_id = save(conv_id, test_user["id"], confidence=0.3)

        response = await client.get(
            "/api/rag/suggestions/pending", headers=auth_headers)

        assert response.status_code == 200
        items = {s["id"]: s for s in response.json()["suggestions"]}

        assert items[medium_id]["confidence"] == 0.72
        assert items[medium_id]["confidence_level"] == "medium"
        assert items[high_id]["confidence_level"] == "high"
        assert items[low_id]["confidence_level"] == "low"

        item = items[medium_id]
        assert item["feedback_type"] == "persona_consistency"
        # 建议JSON被解析为dict
        assert item["suggestion"]["deviation"] == SUGGESTION_PAYLOAD["deviation"]
        assert item["suggestion"]["suggestion"] == SUGGESTION_PAYLOAD["suggestion"]
        # 对话内容回填（收件箱直接可读上下文）
        assert item["user_input"] == "介绍一下你自己"
        assert item["bot_reply"] == "我是一个AI助手。"
        assert item["character"] == "march7th"
        assert item["conversation_id"] == conv_id

    async def test_stats_scope_self_and_all(
        self, client: AsyncClient, auth_headers: dict, admin_auth_headers: dict,
        suggestion_db: dict, test_user: dict
    ):
        """建议闭环统计: 普通用户只看自己(scope=self), 管理员可看全局(scope=all)"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")

        save = suggestion_db["save_suggestion"]
        other_id = suggestion_db["other_user"]["id"]
        # 用户A: 2条auto待确认 + 1条auto已确认(已写RAG) + 1条用户手动反馈待处理
        save(conv_id, test_user["id"], origin='auto', status='pending')
        save(conv_id, test_user["id"], origin='auto', status='pending')
        save(conv_id, test_user["id"], origin='auto', status='confirmed', rag_updated=True)
        save(conv_id, test_user["id"], origin='user', status='pending')
        # 用户B: 1条auto已驳回 + 1条auto待确认
        save(conv_id, other_id, origin='auto', status='rejected')
        save(conv_id, other_id, origin='auto', status='pending')

        # 普通用户: 只统计自己的建议闭环
        response = await client.get(
            "/api/rag/suggestions/stats", headers=auth_headers)

        assert response.status_code == 200
        stats = response.json()["stats"]
        assert stats["scope"] == "self"
        assert stats["auto_generated"] == 3
        assert stats["auto_confirmed"] == 1
        assert stats["auto_rejected"] == 0
        assert stats["auto_pending"] == 2
        assert stats["pending_total"] == 3  # auto 2 + 手动反馈 1
        assert stats["confirm_rate"] == 1.0
        assert stats["rag_updated_total"] == 1

        # 普通用户伪造 scope=all 仍降级为 self
        response = await client.get(
            "/api/rag/suggestions/stats?scope=all", headers=auth_headers)
        stats = response.json()["stats"]
        assert stats["scope"] == "self"
        assert stats["auto_generated"] == 3

        # 管理员: scope=all 查看全局建议闭环
        response = await client.get(
            "/api/rag/suggestions/stats?scope=all", headers=admin_auth_headers)

        assert response.status_code == 200
        stats = response.json()["stats"]
        assert stats["scope"] == "all"
        assert stats["auto_generated"] == 5
        assert stats["auto_confirmed"] == 1
        assert stats["auto_rejected"] == 1
        assert stats["auto_pending"] == 3
        # 全局待处理: A(auto 2 + 手动反馈 1) + B(auto 1)
        assert stats["pending_total"] == 4
        assert stats["confirm_rate"] == 0.5

    async def test_conversation_suggestions_access_control(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """按对话查询建议: 本人可见, 他人对话403, 不存在的对话404"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "问题", "回答")
        suggestion_db["save_suggestion"](conv_id, test_user["id"], origin='auto')

        response = await client.get(
            f"/api/rag/suggestions/conversation/{conv_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["suggestions"][0]["conversation_id"] == conv_id
        assert data["suggestions"][0]["user_input"] == "问题"

        # 其他用户无权访问该对话的建议
        response = await client.get(
            f"/api/rag/suggestions/conversation/{conv_id}",
            headers=suggestion_db["other_headers"])
        assert response.status_code == 403

        # 不存在的对话
        response = await client.get(
            "/api/rag/suggestions/conversation/99999", headers=auth_headers)
        assert response.status_code == 404


class TestSuggestionConfirmReject:
    """闭环建议确认/驳回: 确认写RAG(trust=1.0), 驳回永不写"""

    async def test_confirm_writes_rag_with_full_trust(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """确认建议: 知识写入RAG(metadata trust=1.0), 状态confirmed, rag_updated落库"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th",
            "介绍一下你自己", "我是一个AI助手。")
        detail_id = suggestion_db["save_suggestion"](
            conv_id, test_user["id"], origin='auto', confidence=0.72,
            context_snapshot={
                "user_input": "介绍一下你自己",
                "bot_reply": "我是一个AI助手。",
                "model_name": "march7th",
            })

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/confirm", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rag_updated"] is True

        # 写入 RAG: trust=1.0(权威性来自人工确认), 记录来源与确认者
        entries = suggestion_db["calls"]["add_knowledge_entry"]
        assert len(entries) == 1
        metadata = entries[0]["metadata"]
        assert metadata["trust"] == 1.0
        assert metadata["origin"] == "auto"
        assert metadata["feedback_id"] == detail_id
        assert metadata["confidence"] == 0.72
        assert metadata["confirmed_by"] == "user"
        assert "画像修正" in entries[0]["content"]
        assert "介绍一下你自己" in entries[0]["content"]

        # 状态与 rag_updated 已落库
        detail = database.get_feedback_detail_by_id(suggestion_db["db"], detail_id)
        assert detail["suggestion_status"] == "confirmed"
        assert detail["confirmed"] == 1
        assert detail["rag_updated"] == 1

    async def test_confirm_upgrades_weak_auto_written_entry(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """曾被弱权重自动写入的建议: 确认后升级原条目为 trust=1.0, 不重复写入"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")
        detail_id = suggestion_db["save_suggestion"](
            conv_id, test_user["id"], origin='auto', confidence=0.9)

        # 模拟该建议曾被弱权重自动写入 ChromaDB
        suggestion_db["collection"].get = MagicMock(return_value={
            "ids": ["weak-entry-001"],
            "metadatas": [{"source": "feedback", "origin": "auto",
                           "trust": 0.45, "feedback_id": detail_id}],
        })

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/confirm", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["upgraded_weak_entry"] is True
        assert data["rag_updated"] is True

        # 升级原条目而非新增写入
        assert suggestion_db["calls"]["add_knowledge_entry"] == []
        update_kwargs = suggestion_db["calls"]["collection_update"][0]
        assert update_kwargs["ids"] == ["weak-entry-001"]
        assert update_kwargs["metadatas"][0]["trust"] == 1.0
        assert update_kwargs["metadatas"][0]["feedback_id"] == detail_id

    async def test_confirm_idempotent_and_rejected_mutex(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """已确认建议重复确认幂等返回且不重复写RAG, 已驳回建议不能再确认"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")

        save = suggestion_db["save_suggestion"]
        confirmed_id = save(conv_id, test_user["id"], status='confirmed')
        rejected_id = save(conv_id, test_user["id"], status='rejected')

        response = await client.post(
            f"/api/rag/suggestions/{confirmed_id}/confirm", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["already_confirmed"] is True
        # 幂等路径不触发新的 RAG 写入
        assert suggestion_db["calls"]["add_knowledge_entry"] == []

        response = await client.post(
            f"/api/rag/suggestions/{rejected_id}/confirm", headers=auth_headers)
        assert response.status_code == 400

    async def test_reject_prevents_rag_write(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """驳回建议: 状态rejected, 永不写入RAG"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")
        detail_id = suggestion_db["save_suggestion"](
            conv_id, test_user["id"], origin='auto')

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/reject", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "不会写入" in data["message"]

        assert suggestion_db["calls"]["add_knowledge_entry"] == []
        assert suggestion_db["calls"]["collection_update"] == []

        detail = database.get_feedback_detail_by_id(suggestion_db["db"], detail_id)
        assert detail["suggestion_status"] == "rejected"
        assert detail["rag_updated"] == 0

    async def test_reject_idempotent_and_confirmed_mutex(
        self, client: AsyncClient, auth_headers: dict, suggestion_db: dict, test_user: dict
    ):
        """已驳回建议重复驳回幂等返回, 已确认建议不能再驳回"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")

        save = suggestion_db["save_suggestion"]
        rejected_id = save(conv_id, test_user["id"], status='rejected')
        confirmed_id = save(conv_id, test_user["id"], status='confirmed')

        response = await client.post(
            f"/api/rag/suggestions/{rejected_id}/reject", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["already_rejected"] is True

        response = await client.post(
            f"/api/rag/suggestions/{confirmed_id}/reject", headers=auth_headers)
        assert response.status_code == 400

    async def test_other_user_cannot_confirm_or_reject(
        self, client: AsyncClient, auth_headers: dict,
        suggestion_db: dict, test_user: dict
    ):
        """其他普通用户无权确认/驳回他人建议, 403路径不改变建议状态"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")
        detail_id = suggestion_db["save_suggestion"](
            conv_id, test_user["id"], origin='auto')

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/confirm",
            headers=suggestion_db["other_headers"])
        assert response.status_code == 403

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/reject",
            headers=suggestion_db["other_headers"])
        assert response.status_code == 403

        # 越权请求不改变建议状态，也未触发任何 RAG 写入
        detail = database.get_feedback_detail_by_id(suggestion_db["db"], detail_id)
        assert detail["suggestion_status"] == "pending"
        assert suggestion_db["calls"]["add_knowledge_entry"] == []

    async def test_admin_can_confirm_others_suggestion(
        self, client: AsyncClient, admin_auth_headers: dict,
        suggestion_db: dict, test_user: dict
    ):
        """管理员确认他人建议: 不再误报500, 状态confirmed且写入RAG(回归)"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th",
            "介绍一下你自己", "我是一个AI助手。")
        detail_id = suggestion_db["save_suggestion"](
            conv_id, test_user["id"], origin='auto',
            context_snapshot={
                "user_input": "介绍一下你自己",
                "bot_reply": "我是一个AI助手。",
            })

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/confirm",
            headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rag_updated"] is True

        # 建议以归属人身份落库: confirmed + rag_updated
        detail = database.get_feedback_detail_by_id(suggestion_db["db"], detail_id)
        assert detail["suggestion_status"] == "confirmed"
        assert detail["confirmed"] == 1
        assert detail["rag_updated"] == 1
        assert len(suggestion_db["calls"]["add_knowledge_entry"]) == 1

    async def test_admin_can_reject_others_suggestion(
        self, client: AsyncClient, admin_auth_headers: dict,
        suggestion_db: dict, test_user: dict
    ):
        """管理员驳回他人建议: 不再误报500, 状态rejected且永不写RAG(回归)"""
        import database

        conv_id = database.save_conversation(
            suggestion_db["db"], test_user["id"], "march7th", "你好", "你好呀！")
        detail_id = suggestion_db["save_suggestion"](
            conv_id, test_user["id"], origin='auto')

        response = await client.post(
            f"/api/rag/suggestions/{detail_id}/reject",
            headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "不会写入" in data["message"]

        detail = database.get_feedback_detail_by_id(suggestion_db["db"], detail_id)
        assert detail["suggestion_status"] == "rejected"
        assert detail["rag_updated"] == 0
        assert suggestion_db["calls"]["add_knowledge_entry"] == []
