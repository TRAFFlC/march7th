"""
对话、语音输入、流式对话、评分反馈与历史记录路由
"""
import asyncio
import base64
import json
import logging
import threading
from datetime import datetime, UTC
from typing import Dict, Optional, Tuple, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from rate_limiter import rate_limiter, get_client_ip
from ..deps import (
    get_current_user,
    set_last_debug_info,
    ensure_conversation_access,
    export_to_markdown,
    export_to_json,
    MAX_CHAT_HISTORY_LIMIT,
    _security_filter as security_filter,
)
from ..schemas import (
    ChatRequest,
    VoiceInputRequest,
    RatingRequest,
    FeedbackDetailRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# 自动画像一致性检测（反馈闭环自动生效）
# 节流：每用户每角色每 N 轮对话检测一次（AUTO_CONSISTENCY_INTERVAL，默认 3 轮）
# ---------------------------------------------------------------------------
_consistency_turn_counters: Dict[Tuple[int, str], int] = {}
_consistency_counters_lock = threading.Lock()


def _should_run_consistency_check(user_id: int, character_id: Optional[str]) -> bool:
    import config as app_config

    if not character_id:
        return False

    interval = max(1, getattr(app_config, "AUTO_CONSISTENCY_INTERVAL", 3))
    key = (user_id, character_id)
    with _consistency_counters_lock:
        _consistency_turn_counters[key] = _consistency_turn_counters.get(key, 0) + 1
        return _consistency_turn_counters[key] % interval == 0


def _build_consistency_history(session_id, exclude_conversation_id: int, limit: int = 6) -> list:
    """从数据库取该会话最近几轮对话（不含当前轮）作为检测上下文。"""
    from database import get_db, get_session_conversations

    if not session_id:
        return []

    try:
        db = get_db()
        conversations = get_session_conversations(db, session_id)
    except Exception:
        return []

    history = []
    for conv in reversed(conversations):
        if conv.get('id') == exclude_conversation_id:
            continue
        history.append({"role": "user", "content": conv.get('user_input', '')})
        history.append({"role": "assistant", "content": conv.get('bot_reply', '')})
        if len(history) >= limit:
            break
    return history[:limit]


def _run_persona_consistency_check_sync(conversation_id: int, user_id: int, character_id: Optional[str]):
    """同步执行的画像一致性检测（在后台线程中运行，不阻塞对话返回）。"""
    from database import (
        get_db,
        get_conversation_by_id,
        get_settings,
        save_feedback_detail,
    )
    from character_config import CharacterConfigManager
    from rag_iteration import RAGIterationManager, get_iteration_api_config
    from llm_provider import get_provider
    import config as app_config

    try:
        db = get_db()
        conv = get_conversation_by_id(db, conversation_id)
        if not conv or conv.get('user_id') != user_id:
            return

        char = CharacterConfigManager().get_character(conv.get('character', ''))
        if char is None:
            logger.info("[AutoConsistency] 未找到角色配置，跳过自动检测")
            return

        api_configs = get_iteration_api_config(char)
        if not api_configs:
            # 与现有迭代修正的 API 校验规则一致：未配置独立 API（或仅 ollama）时跳过，不报错
            logger.info("[AutoConsistency] 角色未配置可用的 iteration API，跳过自动检测")
            return

        character_info = char.llm_config.system_prompt
        user_input = conv.get('user_input', '')
        bot_reply = conv.get('bot_reply', '')
        history = _build_consistency_history(
            conv.get('session_id'), conversation_id)

        providers = [get_provider(c) for c in api_configs]
        iteration_manager = RAGIterationManager(llm_providers=providers)

        result = iteration_manager.process_feedback(
            feedback_type="persona_consistency",
            conversation_data={
                "user_input": user_input,
                "bot_reply": bot_reply,
                "model_name": conv.get('character', ''),
            },
            character_info=character_info,
            conversation_history=history,
        )

        if not isinstance(result, dict) or result.get("error") or result.get("parse_error"):
            logger.info("[AutoConsistency] 检测未得到有效结果，跳过: %s",
                        (result or {}).get("error", "parse_error") if isinstance(result, dict) else result)
            return

        if result.get("is_consistent", True):
            # 检测认为符合画像：不生成待确认建议，仅记录统计（日志）
            logger.info("[AutoConsistency] 检测结论：符合画像 (confidence=%s)，不生成待确认建议",
                        result.get("confidence"))
            return

        confidence = result.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.5

        suggestion_payload = {
            "is_consistent": False,
            "deviation": result.get("deviation", ""),
            "suggestion": result.get("suggestion", ""),
            "confidence": confidence,
        }

        # 先保存待确认建议（origin=auto，永不直接写 RAG）
        feedback_id = save_feedback_detail(
            db,
            conversation_id=conversation_id,
            user_id=user_id,
            feedback_type="persona_consistency",
            context_snapshot={
                "user_input": user_input,
                "bot_reply": bot_reply,
                "model_name": conv.get('character', ''),
            },
            correction_suggestion=json.dumps(
                suggestion_payload, ensure_ascii=False),
            model_name=conv.get('character', ''),
            origin='auto',
            confidence=confidence,
            suggestion_status='pending',
        )

        if not feedback_id:
            logger.warning("[AutoConsistency] 待确认建议保存失败")
            return

        logger.info(
            "[AutoConsistency] 已生成待确认建议 #%s (confidence=%.2f)",
            feedback_id, confidence)

        # 弱权重自动写入（实验开关，默认关闭）：confidence ≥ 0.85 时写入 trust = confidence × 0.5 的条目
        try:
            settings = get_settings(db)
        except Exception:
            settings = {}
        weak_write_enabled = settings.get(
            "autoWeakWriteEnabled",
            getattr(app_config, "AUTO_WEAK_WRITE_ENABLED", False),
        )
        weak_threshold = getattr(
            app_config, "AUTO_WEAK_WRITE_CONFIDENCE_THRESHOLD", 0.85)
        weak_trust_factor = getattr(
            app_config, "AUTO_WEAK_WRITE_TRUST_FACTOR", 0.5)

        if weak_write_enabled and confidence >= weak_threshold:
            try:
                from persona_manager import get_persona_manager
                from database import (
                    update_feedback_suggestion_json,
                    update_feedback_rag_status,
                )

                knowledge_content = (
                    f"画像修正: {suggestion_payload['deviation']} - {suggestion_payload['suggestion']}"
                    if suggestion_payload['deviation'] or suggestion_payload['suggestion']
                    else None
                )
                if knowledge_content:
                    entry_id = get_persona_manager().add_knowledge_entry(
                        content=knowledge_content,
                        metadata={
                            "source": "feedback",
                            "origin": "auto",
                            "trust": confidence * weak_trust_factor,
                            "confidence": confidence,
                            "feedback_id": feedback_id,
                            "feedback_type": "persona_consistency",
                        },
                    )
                    if entry_id is not None:
                        suggestion_payload["auto_written"] = True
                        suggestion_payload["auto_written_trust"] = round(
                            confidence * weak_trust_factor, 4)
                        update_feedback_suggestion_json(
                            db, feedback_id,
                            json.dumps(suggestion_payload, ensure_ascii=False))
                        update_feedback_rag_status(db, feedback_id, True)
                        logger.info(
                            "[AutoConsistency] 弱权重自动写入 RAG (trust=%.2f, confidence=%.2f)",
                            confidence * weak_trust_factor, confidence)
                    else:
                        logger.info("[AutoConsistency] 弱权重写入被去重跳过")
            except Exception as e:
                logger.warning("[AutoConsistency] 弱权重自动写入失败: %s", e)
    except Exception as e:
        logger.warning("[AutoConsistency] 画像一致性检测异常: %s", e)


def _schedule_persona_consistency_check(conversation_id: Optional[int],
                                        user_id: int,
                                        character_id: Optional[str]):
    """对话完成后异步触发一致性检测（后台线程，不阻塞对话返回）。"""
    if not conversation_id:
        return
    if not _should_run_consistency_check(user_id, character_id):
        return

    thread = threading.Thread(
        target=_run_persona_consistency_check_sync,
        args=(conversation_id, user_id, character_id),
        daemon=True,
        name=f"persona-consistency-{conversation_id}",
    )
    thread.start()
    logger.info("[AutoConsistency] 已调度画像一致性检测 (conversation_id=%s)", conversation_id)


@router.post("/api/chat")
async def chat(data: ChatRequest, request: Request, response: Response, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from database import get_db, save_conversation, create_session, get_session, update_session

    rate_limiter.check(
        f"chat:{user['user_id']}", limit=60, window_seconds=60, response=response
    )

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    is_safe, threats = security_filter.check(data.message.strip())
    if not is_safe:
        threat_types = list(set(t["type"] for t in threats))
        return {
            "success": False,
            "response": "⚠️ 您的输入触发了安全过滤器，请修改后重试。",
            "conversation_id": None,
            "audio": None,
            "debug": {"security_threats": threat_types},
        }

    try:
        db = get_db()
        session_id = data.session_id
        session = None

        if session_id:
            session = get_session(db, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")
            if session['user_id'] != user['user_id']:
                raise HTTPException(status_code=403, detail="无权访问该会话")

        controller = get_controller(user_id=user["user_id"], character_id=data.character_id)

        if not session_id:
            actual_character_id = data.character_id or controller.get_current_character_id()
            if actual_character_id:
                session_id = create_session(
                    db, user['user_id'], actual_character_id)

        if session_id and session:
            controller.switch_session(session_id, user['user_id'])

        response_text, audio_bytes, conversation_id, debug_info = await asyncio.to_thread(
            controller.process_user_input,
            data.message.strip(),
            character_id=data.character_id,
            model_name=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            user_id=user['user_id'],
            emotion=data.emotion,
            session_id=session_id,
        )

        audio_base64 = None
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        if session_id:
            session = get_session(db, session_id)
            update_session(db, session_id,
                           last_message_at=datetime.now(UTC),
                           message_count=session.get('message_count', 0) + 1 if session else 1)

        set_last_debug_info(debug_info)

        # 对话完成后异步触发画像一致性检测（不阻塞对话返回）
        _schedule_persona_consistency_check(
            conversation_id,
            user['user_id'],
            data.character_id or controller.get_current_character_id(),
        )

        rag_info = debug_info.get("rag", {})

        return {
            "success": True,
            "response": response_text,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "audio": audio_base64,
            "emotion": debug_info.get("emotion", "neutral"),
            "rag_info": {
                "enabled": rag_info.get("enabled", False),
                "status": rag_info.get("status", "unknown"),
                "query": data.message.strip(),
                "top_k": rag_info.get("top_k", 0),
                "distance_threshold": rag_info.get("distance_threshold", 0),
                "total_found": len(rag_info.get("documents", [])),
                "documents": rag_info.get("documents", []),
            },
            "debug": {
                "llm_time": debug_info.get("llm", {}).get("generation_time", 0),
                "tts_time": debug_info.get("tts", {}).get("synthesis_time", 0),
                "total_time": debug_info.get("total_time", 0),
            }
        }
    except Exception as e:
        logging.error(f"处理对话失败: {e}", exc_info=True)
        if 'debug_info' in locals():
            set_last_debug_info(debug_info)
        raise HTTPException(status_code=500, detail="处理对话时发生内部错误")


@router.post("/api/voice/input")
async def voice_input(data: VoiceInputRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from database import get_db, save_conversation, create_session, get_session, update_session

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    is_safe, threats = security_filter.check(data.message.strip())
    if not is_safe:
        threat_types = list(set(t["type"] for t in threats))
        return {
            "success": False,
            "response": "⚠️ 您的输入触发了安全过滤器，请修改后重试。",
            "conversation_id": None,
            "audio": None,
            "debug": {"security_threats": threat_types},
        }

    try:
        controller = get_controller(user_id=user["user_id"], character_id=data.character_id)
        db = get_db()

        actual_character_id = data.character_id or controller.get_current_character_id()
        session_id = data.session_id
        session = None

        if session_id:
            session = get_session(db, session_id)
            if session and session['user_id'] == user['user_id']:
                logger.info("[Voice] 复用已有会话: %s", session_id)
            else:
                session = None
                session_id = None

        if not session_id:
            session_id = create_session(
                db, user['user_id'], actual_character_id, title=data.message.strip()[:50])
            logger.info("[Voice] 创建新会话: %s", session_id)

        if session_id and session:
            controller.switch_session(session_id, user['user_id'])

        response_text, audio_bytes, conversation_id, debug_info = await asyncio.to_thread(
            controller.process_user_input,
            data.message.strip(),
            character_id=data.character_id,
            model_name=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            user_id=user['user_id'],
            emotion=data.emotion,
            session_id=session_id,
        )

        audio_base64 = None
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        if session_id:
            session = get_session(db, session_id)
            update_session(db, session_id,
                           last_message_at=datetime.now(UTC),
                           message_count=session.get('message_count', 0) + 1 if session else 1)

        set_last_debug_info(debug_info)

        # 对话完成后异步触发画像一致性检测（不阻塞对话返回）
        _schedule_persona_consistency_check(
            conversation_id,
            user['user_id'],
            actual_character_id,
        )

        rag_info = debug_info.get("rag", {})

        return {
            "success": True,
            "response": response_text,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "audio": audio_base64,
            "emotion": debug_info.get("emotion", "neutral"),
            "rag_info": {
                "enabled": rag_info.get("enabled", False),
                "status": rag_info.get("status", "unknown"),
                "query": data.message.strip(),
                "top_k": rag_info.get("top_k", 0),
                "distance_threshold": rag_info.get("distance_threshold", 0),
                "total_found": len(rag_info.get("documents", [])),
                "documents": rag_info.get("documents", []),
            },
            "debug": {
                "llm_time": debug_info.get("llm", {}).get("generation_time", 0),
                "tts_time": debug_info.get("tts", {}).get("synthesis_time", 0),
                "total_time": debug_info.get("total_time", 0),
            }
        }
    except Exception as e:
        if 'debug_info' in locals():
            set_last_debug_info(debug_info)
        raise HTTPException(status_code=500, detail="处理语音输入时发生内部错误")


async def stream_chat_response(
    controller,
    user_input: str,
    character_id: str,
    model_name: str,
    temperature: float,
    top_p: float,
    user_id: int,
    emotion: str = "neutral",
    session_id: str = None,
) -> AsyncGenerator[str, None]:
    from database import get_db, create_session, get_session, update_session

    logger.info("[API] stream_chat_response called with session_id: %s", session_id)
    db = get_db()
    actual_session_id = session_id
    session = None

    if actual_session_id:
        session = get_session(db, actual_session_id)
        logger.debug(
            "[API] Found session: %s, user_id match: %s", session is not None, session and session['user_id'] == user_id)
        if not session or session['user_id'] != user_id:
            actual_session_id = None
            session = None
        else:
            controller.switch_session(actual_session_id, user_id)
            logger.info("[API] Switched to session: %s", actual_session_id)

    if not actual_session_id:
        actual_character_id = character_id or controller.get_current_character_id()
        if actual_character_id:
            actual_session_id = create_session(
                db, user_id, actual_character_id)
            logger.info(
                "[API] Created new session: %s for character: %s", actual_session_id, actual_character_id)
        else:
            logger.warning(
                "[API] No character_id available, session will not be created")

    try:
        async for event in controller.process_stream(
            user_input,
            temperature=temperature,
            top_p=top_p,
            character_id=character_id,
            model_name=model_name,
            user_id=user_id,
            emotion=emotion,
            session_id=actual_session_id,
        ):
            event_type = event.get("type")

            if event_type == "text":
                data = json.dumps({"content": event.get(
                    "content", "")}, ensure_ascii=False)
                yield f"event: text\ndata: {data}\n\n"

            elif event_type == "audio":
                data = json.dumps({
                    "audio": event.get("audio", ""),
                    "text": event.get("text", "")
                }, ensure_ascii=False)
                yield f"event: audio\ndata: {data}\n\n"

            elif event_type == "done":
                if actual_session_id:
                    session = get_session(db, actual_session_id)
                    update_session(db, actual_session_id,
                                   last_message_at=datetime.now(UTC),
                                   message_count=session.get('message_count', 0) + 1 if session else 1)
                # 对话完成后异步触发画像一致性检测（不阻塞流式返回）
                _schedule_persona_consistency_check(
                    event.get("conversation_id"),
                    user_id,
                    character_id or controller.get_current_character_id(),
                )
                data = json.dumps({
                    "conversation_id": event.get("conversation_id"),
                    "session_id": actual_session_id,
                    "rag_info": event.get("rag_info"),
                }, ensure_ascii=False)
                yield f"event: done\ndata: {data}\n\n"

            elif event_type == "error":
                data = json.dumps(
                    {"error": event.get("error", "Unknown error")}, ensure_ascii=False)
                yield f"event: error\ndata: {data}\n\n"

    except Exception as e:
        error_data = json.dumps({"error": "流式响应发生错误"}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"


@router.post("/api/chat/stream")
async def chat_stream(data: ChatRequest, request: Request, response: Response, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller

    rate_limiter.check(
        f"chat_stream:{user['user_id']}", limit=60, window_seconds=60, response=response
    )

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    is_safe, threats = security_filter.check(data.message.strip())
    if not is_safe:
        threat_types = list(set(t["type"] for t in threats))
        error_data = json.dumps(
            {"error": "您的输入触发了安全过滤器，请修改后重试。", "security_threats": threat_types},
            ensure_ascii=False,
        )
        return StreamingResponse(
            iter([f"event: error\ndata: {error_data}\n\n"]),
            media_type="text/event-stream",
        )

    controller = get_controller(user_id=user["user_id"], character_id=data.character_id)

    return StreamingResponse(
        stream_chat_response(
            controller=controller,
            user_input=data.message.strip(),
            character_id=data.character_id,
            model_name=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            user_id=user['user_id'],
            emotion=data.emotion,
            session_id=data.session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/api/chat/rating")
async def rate_conversation(data: RatingRequest, user: dict = Depends(get_current_user)):
    from database import get_db, update_rating, set_needs_feedback, get_conversation_by_id
    from persona_manager import get_persona_manager

    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="评分必须在1-5之间")

    db = get_db()
    conv = get_conversation_by_id(db, data.conversation_id)
    ensure_conversation_access(conv, user, "对话记录不存在")

    success = update_rating(db, data.conversation_id, data.rating)
    if not success:
        raise HTTPException(status_code=500, detail="评分保存失败")

    if data.rating >= 4:
        persona_manager = get_persona_manager()
        persona_manager.save_dialogue(
            user_input=conv.get('user_input', ''),
            assistant_response=conv.get('bot_reply', ''),
            rating=data.rating,
        )
        return {
            "success": True,
            "message": "评分已保存，对话已加入知识库",
            "needs_feedback": False
        }
    else:
        set_needs_feedback(db, data.conversation_id, True)
        return {
            "success": True,
            "message": "评分已保存，请提供详细反馈以帮助我们改进",
            "needs_feedback": True
        }


@router.post("/api/chat/feedback")
async def submit_feedback_detail(data: FeedbackDetailRequest, user: dict = Depends(get_current_user)):
    from database import get_db, save_feedback_detail, get_conversation_by_id
    from feedback_types import FeedbackType
    from rag_iteration import RAGIterationManager
    from llm_provider import get_provider
    from character_config import CharacterConfigManager

    valid_types = [ft.value for ft in FeedbackType]
    if data.feedback_type not in valid_types and data.feedback_type != 'general':
        raise HTTPException(
            status_code=400, detail=f"无效的反馈类型，可选值: {', '.join(valid_types)}, general")

    db = get_db()
    conv = get_conversation_by_id(db, data.conversation_id)
    ensure_conversation_access(conv, user, "对话记录不存在")

    manager = CharacterConfigManager()
    char = manager.get_character(conv.get('character', ''))
    character_info = char.llm_config.system_prompt if char else ""

    providers = []
    if char:
        from rag_iteration import get_iteration_api_config
        iteration_api_configs = get_iteration_api_config(char)
        providers = [get_provider(config) for config in iteration_api_configs]

    iteration_manager = RAGIterationManager(llm_providers=providers if providers else None)

    conversation_data = {
        "user_input": conv.get("user_input", ""),
        "bot_reply": conv.get("bot_reply", ""),
        "model_name": conv.get("character", ""),
    }

    try:
        analysis_result = await asyncio.wait_for(
            asyncio.to_thread(
                iteration_manager.process_feedback,
                feedback_type=data.feedback_type,
                conversation_data=conversation_data,
                character_info=character_info,
            ),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        iteration_manager.cancel()
        return {
            "success": False,
            "error": "RAG迭代分析超时，请稍后重试",
            "timeout": True,
        }

    feedback_id = save_feedback_detail(
        db,
        conversation_id=data.conversation_id,
        user_id=user['user_id'],
        feedback_type=data.feedback_type,
        context_snapshot=conversation_data,
        correction_suggestion=json.dumps(analysis_result, ensure_ascii=False) if isinstance(
            analysis_result, dict) else str(analysis_result),
        model_name=conversation_data.get("model_name", ""),
    )

    if not feedback_id:
        raise HTTPException(status_code=500, detail="反馈保存失败")

    return {
        "success": True,
        "message": "反馈已保存，分析完成",
        "feedback_id": feedback_id,
        "analysis": analysis_result
    }


@router.get("/api/chat/feedback/stats")
async def get_feedback_stats(user: dict = Depends(get_current_user), model_name: Optional[str] = None):
    from database import get_db, get_think_leak_stats

    db = get_db()
    stats = get_think_leak_stats(db, model_name=model_name)

    return {"success": True, "stats": stats}


@router.get("/api/chat/history")
async def get_chat_history(user: dict = Depends(get_current_user), limit: int = 20):
    from database import get_db, get_conversations

    limit = min(limit, MAX_CHAT_HISTORY_LIMIT)
    db = get_db()
    conversations = get_conversations(db, user['user_id'], limit)

    result = []
    for conv in conversations:
        result.append({
            "id": conv['id'],
            "character": conv['character'],
            "user_input": conv['user_input'],
            "bot_reply": conv['bot_reply'],
            "rating": conv['rating'],
            "timestamp": str(conv['timestamp']) if conv.get('timestamp') else None,
            "session_id": conv.get('session_id'),
        })

    return {"success": True, "conversations": result}


@router.put("/api/chat/sessions/{session_id}/title")
async def update_session_title(session_id: str, title_data: dict, user: dict = Depends(get_current_user)):
    from database import get_db, update_conversation_title
    db = get_db()
    success = update_conversation_title(
        db, session_id, user['user_id'], title_data.get('title', ''))
    if success:
        return {"success": True, "message": "标题更新成功"}
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/api/chat/search")
async def search_user_conversations(keyword: Optional[str] = None, character: Optional[str] = None,
                                    limit: int = 50, offset: int = 0,
                                    user: dict = Depends(get_current_user)):
    from database import search_conversations, count_search_results, get_db
    db = get_db()
    results = search_conversations(db, keyword=keyword, user_id=user['user_id'],
                                   character=character, limit=limit, offset=offset)
    total = count_search_results(
        db, keyword=keyword, user_id=user['user_id'], character=character)
    return {"success": True, "results": results, "total": total, "limit": limit, "offset": offset}


@router.post("/api/chat/clear")
async def clear_chat_history(user: dict = Depends(get_current_user)):
    from voice_chat import get_controller

    controller = get_controller(user_id=user["user_id"])
    controller.clear_history()

    return {"success": True, "message": "对话历史已清除"}


@router.get("/api/conversations/{conv_id}/export")
async def export_conversation(
    conv_id: int,
    format: str = "markdown",
    user: dict = Depends(get_current_user)
):
    from database import get_db, get_conversation_by_user

    db = get_db()
    conversation = get_conversation_by_user(db, conv_id, user['user_id'])

    if not conversation:
        raise HTTPException(status_code=404, detail="对话记录不存在")

    character = conversation.get('character', '未知')
    timestamp = str(conversation.get('timestamp', ''))
    safe_timestamp = timestamp.replace(
        ' ', '_').replace(':', '-').replace('.', '-')

    if format == "json":
        content = export_to_json(conversation)
        filename = f"对话记录_{character}_{safe_timestamp}.json"
        return {
            "success": True,
            "filename": filename,
            "content": content,
            "format": "json"
        }
    else:
        content = export_to_markdown(conversation)
        filename = f"对话记录_{character}_{safe_timestamp}.md"
        return {
            "success": True,
            "filename": filename,
            "content": content,
            "format": "markdown"
        }
