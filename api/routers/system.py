"""
系统状态、安全过滤器、桌宠与配置路由
"""
import asyncio
import json
import os
import glob
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from personal_config import PATH_CONFIG
from ..deps import (
    get_current_user,
    get_admin_user,
    _security_filter as security_filter,
)
from ..deps import logger

router = APIRouter()


@router.get("/api/pet/emotion")
async def pet_emotion_stream(user: dict = Depends(get_current_user)):

    async def emotion_generator():
        last_emotion = "neutral"
        while True:
            try:
                from voice_chat import get_controller
                controller = get_controller(user_id=user["user_id"])
                if controller.llm._last_debug_info:
                    current_emotion = controller.llm._last_debug_info.get(
                        "emotion", "neutral")
                else:
                    current_emotion = "neutral"
                if current_emotion != last_emotion:
                    data = json.dumps(
                        {"emotion": current_emotion}, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    last_emotion = current_emotion
            except Exception:
                pass
            await asyncio.sleep(2)

    return StreamingResponse(
        emotion_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/api/security/status")
async def get_security_status(user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "enabled": security_filter.enabled,
        "intercept_count": len(security_filter.intercept_log),
    }


@router.get("/api/security/log")
async def get_security_log(limit: int = 100, admin: dict = Depends(get_admin_user)):
    return {
        "success": True,
        "log": security_filter.get_intercept_log(limit=limit),
    }


@router.put("/api/security/toggle")
async def toggle_security_filter(enabled: bool, admin: dict = Depends(get_admin_user)):
    security_filter.enabled = enabled
    return {
        "success": True,
        "enabled": security_filter.enabled,
        "message": f"安全过滤器已{'启用' if enabled else '禁用'}",
    }


@router.get("/api/system/status")
async def get_system_status(user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from tts_service import check_gpu_memory

    controller = get_controller(user_id=user["user_id"])
    status = controller.get_status()

    return {
        "success": True,
        "status": {
            "llmActive": status['llm_active'],
            "ttsActive": status['tts_active'],
            "gpuMemoryMb": status['gpu_memory_mb'],
            "historyTurns": status['history_turns'],
            "currentCharacter": status.get('current_character_name'),
        }
    }


@router.get("/api/system/backgrounds")
async def get_background_images():
    images_dir = PATH_CONFIG.get("images_dir", "")
    logger.debug("[Background] 检查目录: %s", images_dir)

    if not os.path.exists(images_dir):
        logger.warning("[Background] 目录不存在: %s", images_dir)
        return {"success": False, "images": []}

    patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
    images = []
    for pattern in patterns:
        found = glob.glob(os.path.join(images_dir, pattern))
        logger.debug("[Background] 模式 %s 找到 %s 个文件", pattern, len(found))
        images.extend(found)

    logger.info("[Background] 总共找到 %s 个图片文件", len(images))

    image_names = [os.path.basename(f) for f in images]

    image_urls = [f"/images/{quote(name)}" for name in image_names[:20]]
    logger.debug("[Background] 返回 %s 个URL", len(image_urls))

    return {"success": True, "images": image_urls}
