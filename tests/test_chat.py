"""
Chat API 端点测试
测试聊天、历史记录、评分、LLM 和 TTS 相关 API
"""

import base64
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

import pytest
from httpx import AsyncClient

from tests.mock_services import (
    MockOllamaService,
    MockTTSService,
    create_minimal_wav_bytes,
    get_mock_llm_response,
)


@pytest.fixture
def mock_voice_chat_controller():
    """Mock VoiceChatController"""
    controller = MagicMock()
    controller.process_user_input = MagicMock(
        return_value=(
            "这是一个模拟的回复消息",
            create_minimal_wav_bytes(),
            1,
            {
                "llm": {"generation_time": 0.5, "input_tokens": 10, "output_tokens": 20},
                "tts": {"synthesis_time": 0.3, "audio_size_bytes": 44},
                "total_time": 0.8,
            },
        )
    )
    controller.clear_history = MagicMock(return_value=None)
    controller.save_feedback = MagicMock(return_value=True)
    controller.synthesize_audio = MagicMock(return_value=create_minimal_wav_bytes())
    controller.llm_chat = MagicMock(
        return_value=(
            "LLM 模拟回复",
            {
                "model": "deepseek-r1:8b",
                "response_time": 0.5,
                "input_tokens": 10,
                "output_tokens": 20,
                "history_turns": 0,
                "use_rag": True,
            },
        )
    )
    controller.get_status = MagicMock(
        return_value={
            "llm_active": False,
            "tts_active": False,
            "gpu_memory_mb": 0,
            "history_turns": 0,
            "current_character_name": None,
        }
    )
    return controller


@pytest.fixture
def mock_tts_service():
    """Mock TTSService"""
    service = MagicMock()
    service.synthesize = MagicMock(return_value=create_minimal_wav_bytes())
    service.start = MagicMock(return_value=True)
    service.stop = MagicMock(return_value=True)
    service._is_running = MagicMock(return_value=False)
    return service


@pytest.fixture
def mock_db_functions(test_db):
    """Mock database functions for chat tests"""
    import database

    original_functions = {
        "get_db": database.get_db,
        "save_conversation": getattr(database, "save_conversation", None),
        "get_conversations": getattr(database, "get_conversations", None),
        "update_rating": getattr(database, "update_rating", None),
        "save_llm_test_conversation": getattr(database, "save_llm_test_conversation", None),
        "get_conversation_by_id": getattr(database, "get_conversation_by_id", None),
        "set_needs_feedback": getattr(database, "set_needs_feedback", None),
    }

    def mock_get_db():
        return test_db

    def mock_save_conversation(db, user_id, character, user_input, bot_reply):
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (user_id, character, user_input, bot_reply) VALUES (?, ?, ?, ?)",
                (user_id, character, user_input, bot_reply),
            )
            return cursor.lastrowid

    def mock_get_conversations(db, user_id, limit=50):
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mock_update_rating(db, conversation_id, rating):
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE conversations SET rating = ? WHERE id = ?",
                (rating, conversation_id),
            )
            return cursor.rowcount > 0

    def mock_save_llm_test_conversation(
        db,
        user_id,
        model,
        user_input,
        bot_reply,
        character_id=None,
        temperature=1.0,
        top_p=0.9,
        use_rag=True,
        response_time=None,
        input_tokens=None,
        output_tokens=None,
    ):
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO llm_test_conversations 
                   (user_id, model, character_id, user_input, bot_reply, temperature, top_p, use_rag, response_time, input_tokens, output_tokens)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    model,
                    character_id,
                    user_input,
                    bot_reply,
                    temperature,
                    top_p,
                    1 if use_rag else 0,
                    response_time,
                    input_tokens,
                    output_tokens,
                ),
            )
            return cursor.lastrowid

    def mock_get_conversation_by_id(db, conversation_id):
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def mock_set_needs_feedback(db, conversation_id, needs_feedback):
        return True

    database.get_db = mock_get_db
    database.save_conversation = mock_save_conversation
    database.get_conversations = mock_get_conversations
    database.update_rating = mock_update_rating
    database.save_llm_test_conversation = mock_save_llm_test_conversation
    database.get_conversation_by_id = mock_get_conversation_by_id
    database.set_needs_feedback = mock_set_needs_feedback

    import persona_manager
    original_persona_manager = persona_manager.get_persona_manager
    persona_manager.get_persona_manager = MagicMock(
        return_value=MagicMock(save_dialogue=MagicMock(return_value="test_record_id")))

    yield test_db

    for name, func in original_functions.items():
        if func is not None:
            setattr(database, name, func)
    persona_manager.get_persona_manager = original_persona_manager


class TestChatEndpoint:
    """测试聊天端点 /api/chat"""

    @pytest.mark.asyncio
    async def test_chat_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试成功的聊天请求返回响应和音频"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat",
                json={"message": "你好"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response" in data
        assert data["response"] == "这是一个模拟的回复消息"
        assert "audio" in data
        assert data["audio"] is not None
        assert "conversation_id" in data
        assert "debug" in data
        assert "llm_time" in data["debug"]
        assert "tts_time" in data["debug"]
        assert "total_time" in data["debug"]

    @pytest.mark.asyncio
    async def test_chat_empty_message(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试空消息聊天请求"""
        response = await client.post(
            "/api/chat",
            json={"message": ""},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "消息不能为空" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_chat_whitespace_message(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试仅包含空白的聊天请求"""
        response = await client.post(
            "/api/chat",
            json={"message": "   "},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "消息不能为空" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_chat_unauthorized(
        self,
        client: AsyncClient,
        mock_db_functions,
    ):
        """测试未认证的聊天请求"""
        response = await client.post(
            "/api/chat",
            json={"message": "你好"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_chat_with_character_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试带角色ID的聊天请求"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat",
                json={"message": "你好", "character_id": "march7th"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_chat_with_model_selection(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试选择不同模型的聊天请求"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat",
                json={"message": "你好", "model": "llama3"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_chat_with_temperature_and_top_p(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试带温度和top_p参数的聊天请求"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat",
                json={
                    "message": "你好",
                    "temperature": 0.7,
                    "top_p": 0.8,
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestChatHistory:
    """测试聊天历史端点"""

    @pytest.mark.asyncio
    async def test_get_chat_history(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        test_user,
    ):
        """测试获取聊天历史"""
        import database

        database.save_conversation(
            mock_db_functions,
            test_user["id"],
            "march7th",
            "用户消息",
            "机器人回复",
        )

        response = await client.get(
            "/api/chat/history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "conversations" in data
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["user_input"] == "用户消息"
        assert data["conversations"][0]["bot_reply"] == "机器人回复"

    @pytest.mark.asyncio
    async def test_get_chat_history_unauthorized(
        self,
        client: AsyncClient,
        mock_db_functions,
    ):
        """测试未认证获取聊天历史"""
        response = await client.get("/api/chat/history")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_chat_history_with_limit(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        test_user,
    ):
        """测试带限制数量的聊天历史获取"""
        import database

        for i in range(5):
            database.save_conversation(
                mock_db_functions,
                test_user["id"],
                "march7th",
                f"消息{i}",
                f"回复{i}",
            )

        response = await client.get(
            "/api/chat/history?limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2

    @pytest.mark.asyncio
    async def test_clear_chat_history(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试清除聊天历史"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat/clear",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已清除" in data["message"]
        mock_voice_chat_controller.clear_history.assert_called_once()


class TestRating:
    """测试评分端点"""

    @pytest.mark.asyncio
    async def test_submit_rating_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
        test_user,
    ):
        """测试成功提交评分"""
        import database

        conv_id = database.save_conversation(
            mock_db_functions,
            test_user["id"],
            "march7th",
            "测试消息",
            "测试回复",
        )

        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat/rating",
                json={"conversation_id": conv_id, "rating": 5},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已保存" in data["message"]

    @pytest.mark.asyncio
    async def test_submit_rating_invalid_conversation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试对不存在的对话提交评分"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/chat/rating",
                json={"conversation_id": 99999, "rating": 5},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_submit_rating_out_of_range_low(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试评分低于范围"""
        response = await client.post(
            "/api/chat/rating",
            json={"conversation_id": 1, "rating": 0},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "评分必须在1-5之间" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_submit_rating_out_of_range_high(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试评分高于范围"""
        response = await client.post(
            "/api/chat/rating",
            json={"conversation_id": 1, "rating": 6},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "评分必须在1-5之间" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_submit_rating_unauthorized(
        self,
        client: AsyncClient,
        mock_db_functions,
    ):
        """测试未认证提交评分"""
        response = await client.post(
            "/api/chat/rating",
            json={"conversation_id": 1, "rating": 5},
        )

        assert response.status_code == 403


class TestLLMChatEndpoint:
    """测试 LLM 聊天端点 /api/llm/chat"""

    @pytest.mark.asyncio
    async def test_llm_chat_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试 LLM-only 聊天（无 TTS）"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/llm/chat",
                json={"message": "你好"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response" in data
        assert data["response"] == "LLM 模拟回复"
        assert "debug" in data
        assert "model" in data["debug"]
        assert "response_time" in data["debug"]
        assert "input_tokens" in data["debug"]
        assert "output_tokens" in data["debug"]

    @pytest.mark.asyncio
    async def test_llm_chat_with_rag_enabled(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试启用 RAG 的 LLM 聊天"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/llm/chat",
                json={"message": "你好", "use_rag": True},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_llm_chat_with_rag_disabled(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试禁用 RAG 的 LLM 聊天"""
        mock_voice_chat_controller.llm_chat = MagicMock(
            return_value=(
                "LLM 模拟回复（无RAG）",
                {
                    "model": "deepseek-r1:8b",
                    "response_time": 0.3,
                    "input_tokens": 5,
                    "output_tokens": 15,
                    "history_turns": 0,
                    "use_rag": False,
                },
            )
        )

        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/llm/chat",
                json={"message": "你好", "use_rag": False},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["debug"]["use_rag"] is False

    @pytest.mark.asyncio
    async def test_llm_chat_empty_message(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试空消息的 LLM 聊天"""
        response = await client.post(
            "/api/llm/chat",
            json={"message": ""},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "消息不能为空" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_llm_chat_unauthorized(
        self,
        client: AsyncClient,
        mock_db_functions,
    ):
        """测试未认证的 LLM 聊天"""
        response = await client.post(
            "/api/llm/chat",
            json={"message": "你好"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_llm_chat_with_model_selection(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试选择模型的 LLM 聊天"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/llm/chat",
                json={"message": "你好", "model": "llama3"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_llm_clear(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试清除 LLM 历史"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.post(
                "/api/llm/clear",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_voice_chat_controller.clear_history.assert_called_once()


class TestTTSEndpoint:
    """测试 TTS 端点 /api/tts"""

    @pytest.mark.asyncio
    async def test_tts_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试文本转语音合成"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.get(
                "/api/tts?text=你好世界",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "audio" in data
        assert data["audio"] is not None

        audio_bytes = base64.b64decode(data["audio"])
        assert audio_bytes.startswith(b"RIFF")

    @pytest.mark.asyncio
    async def test_tts_empty_text(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试空文本的 TTS 请求"""
        response = await client.get(
            "/api/tts?text=",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "文本不能为空" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_tts_whitespace_text(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
    ):
        """测试仅包含空白的 TTS 请求"""
        response = await client.get(
            "/api/tts?text=   ",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "文本不能为空" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_tts_unauthorized(
        self,
        client: AsyncClient,
        mock_db_functions,
    ):
        """测试未认证的 TTS 请求"""
        response = await client.get("/api/tts?text=你好")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_tts_with_speed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试带速度参数的 TTS 请求"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.get(
                "/api/tts?text=你好&speed=1.5",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_tts_synthesis_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试 TTS 合成失败"""
        mock_voice_chat_controller.synthesize_audio = MagicMock(return_value=None)

        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            response = await client.get(
                "/api/tts?text=你好",
                headers=auth_headers,
            )

        assert response.status_code == 500
        assert "语音合成失败" in response.json()["detail"]


class TestSystemStatus:
    """测试系统状态端点"""

    @pytest.mark.asyncio
    async def test_get_system_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_functions,
        mock_voice_chat_controller,
    ):
        """测试获取系统状态"""
        with patch("voice_chat.get_controller", return_value=mock_voice_chat_controller):
            with patch("tts_service.check_gpu_memory", return_value=0):
                response = await client.get(
                    "/api/system/status",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "status" in data
        assert "llmActive" in data["status"]
        assert "ttsActive" in data["status"]
        assert "gpuMemoryMb" in data["status"]
        assert "historyTurns" in data["status"]

    @pytest.mark.asyncio
    async def test_get_system_status_unauthorized(
        self,
        client: AsyncClient,
        mock_db_functions,
    ):
        """测试未认证获取系统状态"""
        response = await client.get("/api/system/status")

        assert response.status_code == 403
