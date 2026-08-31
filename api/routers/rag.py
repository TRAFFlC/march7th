"""
RAG 迭代反馈与知识库路由
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

from ..deps import (
    get_current_user,
    ensure_conversation_access,
    _security_filter as security_filter,
)
from ..schemas import (
    RAGIterationRequest,
    RAGConfirmRequest,
    RAGEditConfirmRequest,
)

router = APIRouter()


@router.get("/api/rag/iteration/{conversation_id}")
async def get_rag_iteration(conversation_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_details, get_conversation_by_id

    db = get_db()
    conv = get_conversation_by_id(db, conversation_id)
    ensure_conversation_access(conv, user, "对话不存在")

    feedbacks = get_feedback_details(
        db, conversation_id=conversation_id, limit=1)

    if not feedbacks:
        return {"success": True, "has_result": False}

    feedback = feedbacks[0]
    return {
        "success": True,
        "has_result": True,
        "result": {
            "id": feedback["id"],
            "feedback_type": feedback["feedback_type"],
            "correction_suggestion": feedback["correction_suggestion"],
            "created_at": feedback["created_at"].isoformat() if feedback["created_at"] else None,
            "confirmed": feedback.get("confirmed", False),
        }
    }


@router.post("/api/rag/iteration")
async def trigger_rag_iteration(data: RAGIterationRequest, user: dict = Depends(get_current_user)):
    from database import get_db, get_conversation_by_id
    from rag_iteration import RAGIterationManager, get_iteration_api_config
    from llm_provider import get_provider
    from character_config import CharacterConfigManager
    import asyncio

    db = get_db()
    conv = get_conversation_by_id(db, data.conversation_id)
    ensure_conversation_access(conv, user, "对话不存在")

    manager = CharacterConfigManager()
    char = manager.get_character(conv.get('character', ''))
    character_info = char.llm_config.system_prompt if char else ""

    iteration_api_configs = get_iteration_api_config(char)
    if not iteration_api_configs:
        return {
            "success": False,
            "error": "iteration_api_not_configured",
            "message": "使用本地模型进行迭代分析效果有限，建议配置专用迭代 API（如 OpenRouter 免费模型）以获得更好的分析结果"
        }

    providers = [get_provider(config) for config in iteration_api_configs]
    iteration_manager = RAGIterationManager(llm_providers=providers)

    conversation_data = {
        "user_input": conv.get("user_input", ""),
        "bot_reply": conv.get("bot_reply", ""),
        "model_name": conv.get("character", ""),
    }

    try:
        result = await asyncio.wait_for(
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

    from database import save_feedback_detail
    feedback_id = save_feedback_detail(
        db,
        conversation_id=data.conversation_id,
        user_id=user['user_id'],
        feedback_type=data.feedback_type,
        context_snapshot=conversation_data,
        correction_suggestion=json.dumps(result, ensure_ascii=False) if isinstance(
            result, dict) else str(result),
        model_name=conversation_data.get("model_name", ""),
    )

    return {"success": True, "analysis": result, "feedback_id": feedback_id}


@router.post("/api/rag/iteration/edit-confirm")
async def edit_and_confirm_rag_iteration(data: RAGEditConfirmRequest, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_detail_by_id, confirm_feedback_detail, update_feedback_rag_status

    db = get_db()
    feedback_detail = get_feedback_detail_by_id(db, data.feedback_detail_id)

    if not feedback_detail:
        raise HTTPException(status_code=404, detail="反馈记录不存在")

    if feedback_detail['user_id'] != user['user_id'] and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="无权确认此反馈")

    if feedback_detail.get('confirmed'):
        return {"success": True, "message": "该反馈已确认", "already_confirmed": True}

    if data.edited_suggestion:
        try:
            with db.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE feedback_details SET correction_suggestion = %s WHERE id = %s",
                    (data.edited_suggestion, data.feedback_detail_id)
                )
        except Exception as e:
            logger.warning("[RAG Edit] 更新建议内容失败: %s", e)
            raise HTTPException(status_code=500, detail="更新建议内容失败")

    # user_id 参数是 DB 层的归属过滤条件，须传建议归属人：
    # 管理员代为确认他人反馈时，传操作者 id 会匹配 0 行导致误报 500
    success = confirm_feedback_detail(
        db, data.feedback_detail_id, feedback_detail['user_id'])
    if not success:
        raise HTTPException(status_code=500, detail="确认失败")

    return {
        "success": True,
        "message": "反馈已确认，可以更新到RAG知识库",
        "feedback_detail_id": data.feedback_detail_id
    }


@router.post("/api/rag/iteration/confirm")
async def confirm_rag_iteration(data: RAGConfirmRequest, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_detail_by_id, confirm_feedback_detail, update_feedback_rag_status

    db = get_db()
    feedback_detail = get_feedback_detail_by_id(db, data.feedback_detail_id)

    if not feedback_detail:
        raise HTTPException(status_code=404, detail="反馈记录不存在")

    if feedback_detail['user_id'] != user['user_id'] and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="无权确认此反馈")

    if feedback_detail.get('confirmed'):
        return {"success": True, "message": "该反馈已确认", "already_confirmed": True}

    # 同上：传建议归属人，管理员代确认时不误报 500
    success = confirm_feedback_detail(
        db, data.feedback_detail_id, feedback_detail['user_id'])
    if not success:
        raise HTTPException(status_code=500, detail="确认失败")

    correction_suggestion = feedback_detail.get('correction_suggestion')
    rag_updated = False

    if correction_suggestion:
        try:
            from persona_manager import get_persona_manager
            persona_manager = get_persona_manager()

            suggestion_data = json.loads(correction_suggestion) if isinstance(
                correction_suggestion, str) else correction_suggestion

            if isinstance(suggestion_data, dict):
                knowledge_content = None

                if 'errors' in suggestion_data and suggestion_data['errors']:
                    first_error = suggestion_data['errors'][0]
                    knowledge_content = f"修正: {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
                elif 'deviations' in suggestion_data and suggestion_data['deviations']:
                    first_deviation = suggestion_data['deviations'][0]
                    knowledge_content = f"角色修正: {first_deviation.get('aspect', '')} - {first_deviation.get('suggestion', '')}"
                elif 'forgotten_points' in suggestion_data and suggestion_data['forgotten_points']:
                    first_point = suggestion_data['forgotten_points'][0]
                    knowledge_content = f"记忆点: {first_point.get('point', '')}"
                elif 'overall_suggestion' in suggestion_data:
                    knowledge_content = suggestion_data['overall_suggestion']
                elif 'analyses' in suggestion_data:
                    for analysis_type, analysis in suggestion_data['analyses'].items():
                        if isinstance(analysis, dict) and 'overall_suggestion' in analysis:
                            knowledge_content = analysis['overall_suggestion']
                            break

                if knowledge_content:
                    context_snapshot = feedback_detail.get('context_snapshot')
                    if isinstance(context_snapshot, str):
                        context_snapshot = json.loads(context_snapshot)

                    persona_manager.add_knowledge_entry(
                        content=knowledge_content,
                        metadata={
                            "source": "feedback_correction",
                            "feedback_id": data.feedback_detail_id,
                            "feedback_type": feedback_detail.get('feedback_type'),
                            "user_input": context_snapshot.get('user_input', '') if context_snapshot else '',
                        }
                    )
                    rag_updated = True
                    update_feedback_rag_status(
                        db, data.feedback_detail_id, True)
        except Exception as e:
            logger.warning("[RAG Confirm] 添加知识条目失败: %s", e)

    return {
        "success": True,
        "message": "反馈已确认" + ("，知识条目已添加到RAG" if rag_updated else ""),
        "rag_updated": rag_updated
    }


@router.get("/api/rag/feedback/{conversation_id}")
async def get_conversation_feedback(conversation_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_details, get_conversation_by_id

    db = get_db()
    conv = get_conversation_by_id(db, conversation_id)
    ensure_conversation_access(conv, user, "对话不存在")

    feedbacks = get_feedback_details(
        db, conversation_id=conversation_id, user_id=user['user_id'])

    return {
        "success": True,
        "feedbacks": feedbacks
    }


# ---------------------------------------------------------------------------
# 待确认建议收件箱（反馈闭环自动生效：auto 建议默认进入收件箱，永不直接写 RAG）
# ---------------------------------------------------------------------------

def _parse_suggestion_json(raw) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"suggestion": str(parsed)}
    except (json.JSONDecodeError, TypeError):
        return {"suggestion": str(raw)}


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def _format_suggestion_item(detail: dict) -> dict:
    parsed = _parse_suggestion_json(detail.get('correction_suggestion')) or {}
    context_snapshot = _parse_suggestion_json(detail.get('context_snapshot')) or {}

    confidence = detail.get('confidence')
    if confidence is None:
        confidence = parsed.get('confidence', 0.5)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "id": detail['id'],
        "conversation_id": detail.get('conversation_id'),
        "feedback_type": detail.get('feedback_type'),
        "origin": detail.get('origin', 'user'),
        "confidence": round(confidence, 4),
        "confidence_level": _confidence_level(confidence),
        "suggestion_status": detail.get('suggestion_status', 'pending'),
        "created_at": detail['created_at'].isoformat() if detail.get('created_at') else None,
        "auto_written": bool(parsed.get('auto_written')),
        "auto_written_trust": parsed.get('auto_written_trust'),
        "suggestion": parsed,
        "user_input": detail.get('conv_user_input') or context_snapshot.get('user_input', ''),
        "bot_reply": detail.get('conv_bot_reply') or context_snapshot.get('bot_reply', ''),
        "character": detail.get('conv_character'),
    }


@router.get("/api/rag/suggestions/pending")
async def list_pending_suggestions(user: dict = Depends(get_current_user), limit: int = 50):
    from database import get_db, get_pending_suggestions

    db = get_db()
    limit = max(1, min(limit, 200))
    details = get_pending_suggestions(db, user_id=user['user_id'], origin='auto', limit=limit)

    return {
        "success": True,
        "suggestions": [_format_suggestion_item(d) for d in details],
        "total": len(details),
    }


@router.get("/api/rag/suggestions/stats")
async def get_suggestions_stats(user: dict = Depends(get_current_user), scope: str = "self"):
    from database import get_db, get_feedback_loop_stats

    db = get_db()
    if scope == "all" and user.get('role') == 'admin':
        stats = get_feedback_loop_stats(db)
        stats["scope"] = "all"
    else:
        stats = get_feedback_loop_stats(db, user_id=user['user_id'])
        stats["scope"] = "self"

    return {"success": True, "stats": stats}


@router.get("/api/rag/suggestions/conversation/{conversation_id}")
async def get_conversation_pending_suggestions(conversation_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_pending_suggestions_by_conversation, get_conversation_by_id

    db = get_db()
    conv = get_conversation_by_id(db, conversation_id)
    ensure_conversation_access(conv, user, "对话不存在")

    details = get_pending_suggestions_by_conversation(
        db, conversation_id, user_id=user['user_id'])

    return {
        "success": True,
        "suggestions": [_format_suggestion_item(d) for d in details],
        "total": len(details),
    }


def _extract_knowledge_from_suggestion(parsed: dict, user_input: str, bot_reply: str) -> Optional[str]:
    """从建议 JSON 提取要写入 RAG 的知识内容。"""
    if not isinstance(parsed, dict):
        return None

    knowledge_content = None
    if parsed.get('suggestion'):
        deviation = parsed.get('deviation', '')
        knowledge_content = (
            f"画像修正: {deviation} - {parsed['suggestion']}" if deviation
            else f"修正建议: {parsed['suggestion']}"
        )
    elif parsed.get('errors') and parsed['errors']:
        first_error = parsed['errors'][0]
        knowledge_content = f"修正: {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
    elif parsed.get('deviations') and parsed['deviations']:
        first_deviation = parsed['deviations'][0]
        knowledge_content = f"角色修正: {first_deviation.get('aspect', '')} - {first_deviation.get('suggestion', '')}"
    elif parsed.get('forgotten_points') and parsed['forgotten_points']:
        first_point = parsed['forgotten_points'][0]
        knowledge_content = f"记忆点: {first_point.get('point', '')}"
    elif parsed.get('overall_suggestion'):
        knowledge_content = parsed['overall_suggestion']

    if knowledge_content and user_input and bot_reply:
        knowledge_content = f"用户问: {user_input}\n助手答: {bot_reply}\n修正建议: {knowledge_content}"

    return knowledge_content


def _upgrade_auto_written_entry(persona_manager, feedback_detail_id: int,
                                content: str, metadata: dict) -> bool:
    """若该建议曾被弱权重自动写入，升级为 trust=1.0（权威性来自"谁确认"）。"""
    try:
        collection = persona_manager.load_persona_db()
        existing = collection.get(
            where={"feedback_id": feedback_detail_id}, include=["metadatas"])
        if not existing or not existing.get("ids"):
            return False

        entry_id = existing["ids"][0]
        merged_meta = dict(existing["metadatas"][0] or {})
        merged_meta.update(metadata)
        collection.update(
            ids=[entry_id], documents=[content], metadatas=[merged_meta])
        return True
    except Exception as e:
        logger.warning("[Suggestions Confirm] 升级弱权重条目失败: %s", e)
        return False


@router.post("/api/rag/suggestions/{feedback_detail_id}/confirm")
async def confirm_pending_suggestion(feedback_detail_id: int, user: dict = Depends(get_current_user)):
    from database import (
        get_db,
        get_feedback_detail_by_id,
        confirm_feedback_detail,
        update_feedback_rag_status,
    )
    from persona_manager import get_persona_manager

    db = get_db()
    detail = get_feedback_detail_by_id(db, feedback_detail_id)

    if not detail:
        raise HTTPException(status_code=404, detail="建议不存在")

    if detail['user_id'] != user['user_id'] and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="无权确认此建议")

    status = detail.get('suggestion_status') or 'pending'
    if status == 'confirmed':
        return {"success": True, "message": "该建议已确认", "already_confirmed": True}
    if status == 'rejected':
        raise HTTPException(status_code=400, detail="该建议已被驳回，无法确认")

    origin = detail.get('origin', 'user')
    confidence = detail.get('confidence') or 1.0
    parsed = _parse_suggestion_json(detail.get('correction_suggestion')) or {}
    context_snapshot = _parse_suggestion_json(detail.get('context_snapshot')) or {}

    user_input = context_snapshot.get('user_input', '')
    bot_reply = context_snapshot.get('bot_reply', '')

    rag_updated = False
    upgraded_weak_entry = False
    message = "建议已确认"

    knowledge_content = _extract_knowledge_from_suggestion(parsed, user_input, bot_reply)
    if knowledge_content:
        try:
            persona_manager = get_persona_manager()

            # 用户确认后写入 RAG：trust=1.0，metadata 记录 origin 与 confirmed_by
            metadata = {
                "source": "feedback",
                "origin": origin,
                "trust": 1.0,
                "confidence": confidence,
                "feedback_id": feedback_detail_id,
                "feedback_type": detail.get('feedback_type'),
                "confirmed_by": "user",
            }

            upgraded_weak_entry = _upgrade_auto_written_entry(
                persona_manager, feedback_detail_id, knowledge_content, metadata)
            if upgraded_weak_entry:
                rag_updated = True
                message = "建议已确认，弱权重条目已升级为 trust=1.0"
            else:
                entry_id = persona_manager.add_knowledge_entry(
                    content=knowledge_content, metadata=metadata)
                rag_updated = True
                message = (
                    "建议已确认，知识条目已写入 RAG (trust=1.0)"
                    if entry_id is not None
                    else "建议已确认，RAG 已存在相似条目（去重跳过写入）"
                )
        except Exception as e:
            logger.warning("[Suggestions Confirm] 写入 RAG 失败: %s", e)
            message = "建议已确认，但写入 RAG 失败"

    # 传建议归属人：管理员确认他人建议时，传操作者 id 会匹配 0 行误报 500
    success = confirm_feedback_detail(db, feedback_detail_id, detail['user_id'])
    if not success:
        raise HTTPException(status_code=500, detail="确认失败")

    if rag_updated:
        update_feedback_rag_status(db, feedback_detail_id, True)

    return {
        "success": True,
        "message": message,
        "rag_updated": rag_updated,
        "upgraded_weak_entry": upgraded_weak_entry,
    }


@router.post("/api/rag/suggestions/{feedback_detail_id}/reject")
async def reject_pending_suggestion(feedback_detail_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_detail_by_id, reject_feedback_detail

    db = get_db()
    detail = get_feedback_detail_by_id(db, feedback_detail_id)

    if not detail:
        raise HTTPException(status_code=404, detail="建议不存在")

    if detail['user_id'] != user['user_id'] and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="无权驳回此建议")

    status = detail.get('suggestion_status') or 'pending'
    if status == 'rejected':
        return {"success": True, "message": "该建议已驳回", "already_rejected": True}
    if status == 'confirmed':
        raise HTTPException(status_code=400, detail="该建议已确认，无法驳回")

    # 传建议归属人：管理员驳回他人建议时，传操作者 id 会匹配 0 行误报 500
    success = reject_feedback_detail(db, feedback_detail_id, detail['user_id'])
    if not success:
        raise HTTPException(status_code=500, detail="驳回失败")

    return {"success": True, "message": "建议已驳回，将不会写入 RAG"}


@router.post("/api/rag/update")
async def update_rag_knowledge(user: dict = Depends(get_current_user)):
    from database import get_db, get_unprocessed_rag_feedbacks, update_feedback_rag_status
    from persona_manager import get_persona_manager

    db = get_db()
    feedbacks = get_unprocessed_rag_feedbacks(db, limit=100)

    if not feedbacks:
        return {
            "success": True,
            "message": "没有待更新的知识条目",
            "updated_count": 0
        }

    persona_manager = get_persona_manager()
    updated_count = 0
    errors = []

    for feedback in feedbacks:
        try:
            correction_suggestion = feedback.get('correction_suggestion')
            if not correction_suggestion:
                continue

            suggestion_data = None
            if isinstance(correction_suggestion, str):
                try:
                    suggestion_data = json.loads(correction_suggestion)
                except json.JSONDecodeError:
                    suggestion_data = {"raw_suggestion": correction_suggestion}
            else:
                suggestion_data = correction_suggestion

            knowledge_content = None

            if isinstance(suggestion_data, dict):
                if 'errors' in suggestion_data and suggestion_data['errors']:
                    first_error = suggestion_data['errors'][0]
                    knowledge_content = f"修正: {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
                elif 'deviations' in suggestion_data and suggestion_data['deviations']:
                    first_deviation = suggestion_data['deviations'][0]
                    knowledge_content = f"角色修正: {first_deviation.get('aspect', '')} - {first_deviation.get('suggestion', '')}"
                elif 'forgotten_points' in suggestion_data and suggestion_data['forgotten_points']:
                    first_point = suggestion_data['forgotten_points'][0]
                    knowledge_content = f"记忆点: {first_point.get('point', '')}"
                elif 'overall_suggestion' in suggestion_data:
                    knowledge_content = suggestion_data['overall_suggestion']
                elif 'analyses' in suggestion_data:
                    for analysis_type, analysis in suggestion_data['analyses'].items():
                        if isinstance(analysis, dict) and 'overall_suggestion' in analysis:
                            knowledge_content = analysis['overall_suggestion']
                            break
                        elif isinstance(analysis, dict) and 'errors' in analysis and analysis['errors']:
                            first_error = analysis['errors'][0]
                            knowledge_content = f"修正({analysis_type}): {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
                            break
                elif 'raw_suggestion' in suggestion_data:
                    knowledge_content = suggestion_data['raw_suggestion']

            if knowledge_content:
                context_snapshot = feedback.get('context_snapshot')
                if isinstance(context_snapshot, str):
                    try:
                        context_snapshot = json.loads(context_snapshot)
                    except:
                        context_snapshot = {}

                user_input = context_snapshot.get(
                    'user_input', '') if context_snapshot else feedback.get('conv_user_input', '')
                bot_reply = context_snapshot.get(
                    'bot_reply', '') if context_snapshot else feedback.get('conv_bot_reply', '')

                combined_knowledge = knowledge_content
                if user_input and bot_reply:
                    combined_knowledge = f"用户问: {user_input}\n助手答: {bot_reply}\n修正建议: {knowledge_content}"

                persona_manager.add_knowledge_entry(
                    content=combined_knowledge,
                    metadata={
                        "source": "feedback_correction",
                        "feedback_id": feedback['id'],
                        "feedback_type": feedback.get('feedback_type'),
                        "user_input": user_input,
                    }
                )

                update_feedback_rag_status(db, feedback['id'], True)
                updated_count += 1

        except Exception as e:
            errors.append(f"反馈ID {feedback['id']}: {str(e)}")
            continue

    return {
        "success": True,
        "message": f"成功更新 {updated_count} 条知识到RAG知识库",
        "updated_count": updated_count,
        "total_found": len(feedbacks),
        "errors": errors if errors else None
    }


@router.get("/api/rag/status")
async def get_rag_status(user: dict = Depends(get_current_user)):
    from build_rag import get_rag_collection_info
    from character_config import CharacterConfigManager

    manager = CharacterConfigManager()
    characters = manager.get_all_characters()
    collection_info = get_rag_collection_info()

    status_list = []
    for char in characters:
        coll_name = char.rag_config.collection_name
        matching = [
            c for c in collection_info if c["collection_name"] == coll_name]
        doc_count = matching[0]["document_count"] if matching else 0

        status_list.append({
            "character_id": char.id,
            "character_name": char.name,
            "collection_name": coll_name,
            "rag_enabled": char.rag_config.enabled,
            "document_count": doc_count,
            "has_collection": len(matching) > 0,
        })

    return {"success": True, "status": status_list}


@router.post("/api/rag/build")
async def build_rag_from_txt(request: dict, user: dict = Depends(get_current_user)):
    from build_rag import build_character_rag
    from character_config import CharacterConfigManager

    character_id = request.get("character_id")
    text_content = request.get("text_content", "")

    if not character_id or not text_content.strip():
        return {"success": False, "message": "请提供角色ID和文本内容"}

    manager = CharacterConfigManager()
    character = manager.get_character(character_id)
    if not character:
        return {"success": False, "message": "角色不存在"}

    collection_name = character.rag_config.collection_name
    if not collection_name:
        collection_name = f"{character_id}_knowledge"
        character.rag_config.collection_name = collection_name
        manager.update_character(character)

    try:
        collection, _ = build_character_rag(
            character_id=character_id,
            character_name=character.name,
            collection_name=collection_name,
            text_content=text_content,
        )
        if collection:
            return {"success": True, "message": f"RAG 知识库构建成功，共 {collection.count()} 条文档"}
        else:
            return {"success": False, "message": "RAG 知识库构建失败"}
    except Exception as e:
        return {"success": False, "message": f"构建失败: {str(e)}"}


@router.delete("/api/rag/{collection_name}")
async def delete_rag(collection_name: str, user: dict = Depends(get_current_user)):
    from build_rag import delete_rag_collection

    success = delete_rag_collection(collection_name)
    if success:
        return {"success": True, "message": "RAG 集合已删除"}
    else:
        return {"success": False, "message": "删除失败"}
