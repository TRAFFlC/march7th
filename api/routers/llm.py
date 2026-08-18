"""
LLM 测试与直连对话路由
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from config import LLM_MODEL
from ..deps import get_current_user, set_last_debug_info
from ..schemas import LLMChatRequest, LLMChatDirectRequest, LLMTestRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/llm/chat")
async def llm_chat(data: LLMChatRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from database import get_db, save_llm_test_conversation

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    logger.info(
        "[LLM Chat] 收到请求: model=%s, character_id=%s, use_rag=%s", data.model, data.character_id, data.use_rag)

    try:
        controller = get_controller(user_id=user["user_id"], character_id=data.character_id)

        response_text, debug_info = controller.llm_chat(
            data.message.strip(),
            temperature=data.temperature,
            top_p=data.top_p,
            model_name=data.model,
            use_rag=data.use_rag,
        )

        logger.info(
            "[LLM Chat] 成功: model=%s, response_time=%s", debug_info.get('model'), debug_info.get('response_time'))

        if response_text:
            try:
                preview = response_text[:100].encode(
                    'utf-8', errors='replace').decode('utf-8')
                logger.debug("[LLM Chat] 回复内容: %s...", preview)
            except Exception:
                logger.debug("[LLM Chat] 回复内容: (无法显示，长度=%s)", len(response_text))
        else:
            logger.debug("[LLM Chat] 回复内容: EMPTY")

        db = get_db()
        save_llm_test_conversation(
            db,
            user_id=user['user_id'],
            model=data.model or LLM_MODEL,
            user_input=data.message.strip(),
            bot_reply=response_text,
            character_id=data.character_id,
            temperature=data.temperature,
            top_p=data.top_p,
            use_rag=data.use_rag,
            response_time=debug_info.get('response_time'),
            input_tokens=debug_info.get('input_tokens'),
            output_tokens=debug_info.get('output_tokens'),
        )

        set_last_debug_info(debug_info)

        return {
            "success": True,
            "response": response_text,
            "rag_info": {
                "enabled": debug_info.get("use_rag", False),
                "status": debug_info.get("rag_status", "unknown"),
                "query": data.message.strip(),
                "documents": debug_info.get("rag_documents", []),
                "total_found": len(debug_info.get("rag_documents", [])),
            },
            "debug": {
                "model": debug_info.get("model"),
                "response_time": debug_info.get("response_time", 0),
                "input_tokens": debug_info.get("input_tokens", 0),
                "output_tokens": debug_info.get("output_tokens", 0),
                "history_turns": debug_info.get("history_turns", 0),
                "use_rag": debug_info.get("use_rag"),
            }
        }
    except Exception as e:
        import traceback
        logger.error("[LLM Chat] 错误: %s", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="LLM对话处理失败")


@router.post("/api/llm/clear")
async def llm_clear(user: dict = Depends(get_current_user)):
    from voice_chat import get_controller

    controller = get_controller(user_id=user["user_id"])
    controller.clear_history()

    return {"success": True, "message": "LLM历史已清除"}


@router.post("/api/llm/chat-direct")
async def llm_chat_direct(data: LLMChatDirectRequest, user: dict = Depends(get_current_user)):
    from llm_provider import get_provider, APIConfig

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    logger.info(
        "[LLM Chat Direct] 收到请求: provider=%s, model=%s", data.provider_type, data.model_name)

    try:
        if data.provider_type == "ollama":
            config = APIConfig(
                provider_type="ollama",
                model_name=data.model_name or LLM_MODEL
            )
        else:
            if not data.base_url or not data.api_key or not data.model_name:
                raise HTTPException(
                    status_code=400, detail="API模式需要填写完整的API配置")
            config = APIConfig(
                provider_type="openai_compatible",
                base_url=data.base_url,
                api_key=data.api_key,
                model_name=data.model_name
            )

        provider = get_provider(config)

        messages = []
        if data.system_prompt and data.system_prompt.strip():
            messages.append(
                {"role": "system", "content": data.system_prompt.strip()})
        messages.append({"role": "user", "content": data.message.strip()})

        start_time = time.time()
        result = provider.generate(
            messages,
            temperature=data.temperature,
            top_p=data.top_p,
            max_tokens=2048
        )
        response_time = time.time() - start_time

        response_text = result.get("content", "")
        usage = result.get("usage", {})

        logger.info("[LLM Chat Direct] 成功: response_time=%.2fs", response_time)

        return {
            "success": True,
            "response": response_text,
            "debug": {
                "model": data.model_name,
                "provider": data.provider_type,
                "response_time": round(response_time, 2),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "history_turns": 0,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("[LLM Chat Direct] 错误: %s", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="LLM对话处理失败")


@router.post("/api/llm/test")
async def test_llm_connection(data: LLMTestRequest, user: dict = Depends(get_current_user)):
    from llm_provider import get_provider, APIConfig

    config = APIConfig(
        provider_type=data.provider_type,
        base_url=data.base_url,
        api_key=data.api_key,
        model_name=data.model_name,
    )
    provider = get_provider(config)
    result = provider.test_connection()
    return {"success": True, "test_result": result}
