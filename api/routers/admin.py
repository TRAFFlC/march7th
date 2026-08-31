"""
管理后台路由
"""
import glob as glob_module
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, UTC

from config import CONFIG_CHECK_INTERVAL
from ..deps import (
    get_config_manager,
    get_current_user,
    get_admin_user,
    get_last_debug_info,
    sanitize_debug_info,
    resolve_safe_path,
    export_to_markdown,
    export_to_json,
    MAX_ADMIN_CONVERSATIONS_LIMIT,
    RESOURCES_DIR,
    EMOTIONS_DIR,
    _security_filter as security_filter,
)
from ..schemas import UserCharacterUpdate

router = APIRouter()


@router.get("/api/admin/users")
async def admin_get_users(user: dict = Depends(get_admin_user)):
    from database import get_db, get_all_users

    db = get_db()
    users = get_all_users(db)

    result = []
    for u in users:
        result.append({
            "id": u['id'],
            "username": u['username'],
            "role": u['role'],
            "created_at": str(u['created_at']) if u.get('created_at') else None,
        })

    return {"success": True, "users": result}


@router.get("/api/admin/conversations")
async def admin_get_conversations(
    user: dict = Depends(get_admin_user),
    role: Optional[str] = None,
    limit: int = 100
):
    from database import get_db, get_conversations_by_role

    limit = min(limit, MAX_ADMIN_CONVERSATIONS_LIMIT)
    db = get_db()
    conversations = get_conversations_by_role(db, role, limit)

    result = []
    for conv in conversations:
        result.append({
            "id": conv['id'],
            "username": conv.get('username', ''),
            "role": conv.get('role', ''),
            "character": conv['character'],
            "user_input": conv['user_input'][:100] + "..." if len(conv['user_input']) > 100 else conv['user_input'],
            "bot_reply": conv['bot_reply'][:100] + "..." if len(conv['bot_reply']) > 100 else conv['bot_reply'],
            "rating": conv['rating'],
            "timestamp": str(conv['timestamp']) if conv.get('timestamp') else None,
        })

    return {"success": True, "conversations": result}


@router.get("/api/admin/conversations/search")
async def admin_search_conversations(keyword: Optional[str] = None, user_id: Optional[int] = None,
                                     character: Optional[str] = None,
                                     limit: int = 50, offset: int = 0,
                                     admin: dict = Depends(get_admin_user)):
    from database import search_conversations, count_search_results, get_db
    db = get_db()
    results = search_conversations(db, keyword=keyword, user_id=user_id,
                                   character=character, limit=limit, offset=offset)
    total = count_search_results(
        db, keyword=keyword, user_id=user_id, character=character)
    return {"success": True, "results": results, "total": total, "limit": limit, "offset": offset}


@router.delete("/api/admin/conversations/{conv_id}")
async def admin_delete_conversation(conv_id: int, user: dict = Depends(get_admin_user)):
    from database import get_db, delete_conversation

    db = get_db()
    success = delete_conversation(db, conv_id)

    if not success:
        raise HTTPException(status_code=404, detail="对话记录不存在")

    return {"success": True, "message": "对话已删除"}


@router.get("/api/admin/conversations/{conv_id}/export")
async def admin_export_conversation(
    conv_id: int,
    format: str = "markdown",
    user: dict = Depends(get_admin_user)
):
    from database import get_db, get_conversation_by_id

    db = get_db()
    conversation = get_conversation_by_id(db, conv_id)

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


@router.put("/api/admin/users/{user_id}/role")
async def admin_update_user_role(user_id: int, role: str, user: dict = Depends(get_admin_user)):
    from database import get_db, update_user_role

    if role not in ('user', 'admin'):
        raise HTTPException(status_code=400, detail="无效的角色")

    db = get_db()
    success = update_user_role(db, user_id, role)

    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {"success": True, "message": "角色已更新"}


@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, user: dict = Depends(get_admin_user)):
    from database import get_db, delete_user, get_user_by_id

    db = get_db()
    target = get_user_by_id(db, user_id)

    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target['role'] == 'admin':
        raise HTTPException(status_code=403, detail="不能删除管理员")

    success = delete_user(db, user_id)

    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"success": True, "message": "用户已删除"}


@router.get("/api/admin/user-characters")
async def admin_get_user_characters(user: dict = Depends(get_admin_user)):
    from database import get_db, get_all_user_characters

    manager = get_config_manager()
    global_characters = manager.get_all_characters()

    result = []

    for char in global_characters:
        result.append({
            "id": char.id,
            "name": char.name,
            "avatar_path": char.avatar_path,
            "llm_model": char.llm_config.model,
            "rag_enabled": char.rag_config.enabled,
            "source": "admin",
            "username": "admin",
            "character_data": {
                "name": char.name,
                "avatar_path": char.avatar_path,
                "llm_model": char.llm_config.model,
                "system_prompt": char.llm_config.system_prompt,
                "temperature": char.llm_config.temperature,
                "top_p": char.llm_config.top_p,
                "rag_collection": char.rag_config.collection_name,
                "rag_enabled": char.rag_config.enabled,
            },
        })

    db = get_db()
    user_chars = get_all_user_characters(db)

    for uc in user_chars:
        char_data = json.loads(uc['character_data']) if isinstance(
            uc['character_data'], str) else uc['character_data']
        result.append({
            "id": uc['id'],
            "user_id": uc['user_id'],
            "username": uc.get('username', '未知'),
            "character_id": uc['character_id'],
            "name": char_data.get('name', '未命名'),
            "avatar_path": char_data.get('avatar_path'),
            "llm_model": char_data.get('llm_model'),
            "rag_enabled": char_data.get('rag_enabled', True),
            "source": "user_created",
            "source_id": uc.get('source_id'),
            "character_data": char_data,
            "created_at": str(uc['created_at']) if uc.get('created_at') else None,
        })

    return {"success": True, "characters": result}


@router.post("/api/admin/characters/import/{character_id}")
async def admin_import_global_character(character_id: str, user: dict = Depends(get_admin_user)):
    from database import get_db, create_user_character, check_character_conflict, get_user_character_by_source_id

    manager = get_config_manager()
    char = manager.get_character(character_id)

    if not char:
        raise HTTPException(status_code=404, detail="全局角色不存在")

    db = get_db()

    existing = get_user_character_by_source_id(db, character_id)
    if existing:
        raise HTTPException(status_code=400, detail="该全局角色已被导入，请勿重复导入")

    conflict = check_character_conflict(db, char.name)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"角色冲突：已存在同名角色「{char.name}」，请先处理冲突"
        )

    char_data = {
        "name": char.name,
        "avatar_path": char.avatar_path,
        "llm_model": char.llm_config.model,
        "system_prompt": char.llm_config.system_prompt,
        "temperature": char.llm_config.temperature,
        "top_p": char.llm_config.top_p,
        "gpt_weight": char.tts_config.gpt_weight,
        "sovits_weight": char.tts_config.sovits_weight,
        "ref_audio_path": char.tts_config.ref_audio_path,
        "ref_audio_text": char.tts_config.ref_audio_text,
        "rag_collection": char.rag_config.collection_name,
        "rag_enabled": char.rag_config.enabled,
    }

    import uuid
    new_character_id = f"{character_id}_{uuid.uuid4().hex[:8]}"

    user_char_id = create_user_character(
        db,
        user_id=user['user_id'],
        character_id=new_character_id,
        character_data=char_data,
        source_id=character_id
    )

    if not user_char_id:
        raise HTTPException(status_code=500, detail="导入角色失败")

    return {
        "success": True,
        "message": f"角色「{char.name}」已成功导入",
        "user_character_id": user_char_id,
        "new_character_id": new_character_id,
        "source_id": character_id
    }


@router.put("/api/admin/user-characters/{id}")
async def admin_update_user_character(id: int, data: UserCharacterUpdate, user: dict = Depends(get_admin_user)):
    from database import get_db, update_user_character

    db = get_db()
    success = update_user_character(db, id, data.character_data)

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {"success": True, "message": "角色已更新"}


@router.delete("/api/admin/user-characters/{id}")
async def admin_delete_user_character(id: int, user: dict = Depends(get_admin_user)):
    from database import get_db, delete_user_character

    db = get_db()
    success = delete_user_character(db, id)

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {"success": True, "message": "角色已删除"}


@router.get("/api/admin/resources/list-weights")
async def list_weight_files(user: dict = Depends(get_current_user)):
    resources_dir = RESOURCES_DIR
    if not resources_dir.exists():
        raise HTTPException(status_code=400, detail="资源目录不存在")

    weight_files = []
    for ext in ["*.ckpt", "*.pth"]:
        for f in resources_dir.rglob(ext):
            if f.is_file():
                weight_type = "gpt" if f.suffix == ".ckpt" else "sovits"
                weight_files.append({
                    "path": str(f.absolute()),
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "type": weight_type,
                })

    weight_files.sort(key=lambda x: x["filename"])
    return {"success": True, "files": weight_files}


@router.post("/api/admin/characters/{character_id}/scan-emotions")
async def scan_emotion_folders(character_id: str, data: dict = None, user: dict = Depends(get_current_user)):
    base_path = data.get("base_path") if data else None
    if not base_path:
        base_path = str(EMOTIONS_DIR / character_id)

    try:
        base = resolve_safe_path(base_path, RESOURCES_DIR)
    except HTTPException:
        raise HTTPException(status_code=403, detail="禁止访问资源目录之外的路径")

    if not base.exists():
        raise HTTPException(status_code=400, detail=f"情绪文件夹不存在: {base_path}")

    slicer_list = base / "slicer_opt.list"
    audio_to_text = {}
    if slicer_list.exists():
        try:
            with open(slicer_list, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('|', 3)
                    if len(parts) == 4:
                        audio_basename = Path(parts[0]).name
                        audio_to_text[audio_basename] = parts[3]
        except Exception:
            pass

    emotions = {}
    default_emotions = ['neutral', 'happy',
                        'confused', 'sad', 'angry', 'excited']

    for emotion in default_emotions:
        emotion_dir = base / emotion / character_id
        if emotion_dir.exists():
            wav_files = list(emotion_dir.glob("*.wav"))
            if wav_files:
                audio_path = str(wav_files[0].absolute())
                ref_text = ""

                audio_basename = Path(audio_path).name
                if audio_basename in audio_to_text:
                    ref_text = audio_to_text[audio_basename]

                if not ref_text:
                    dialogue_file = emotion_dir / "dialogues.txt"
                    if dialogue_file.exists():
                        try:
                            with open(dialogue_file, 'r', encoding='utf-8') as f:
                                for line in f:
                                    line = line.strip()
                                    if not line:
                                        continue
                                    if '|' in line:
                                        parts = line.split('|', 1)
                                        if len(parts) == 2 and parts[1].strip():
                                            ref_text = parts[1].strip()
                                            break
                        except Exception:
                            pass

                emotions[emotion] = {
                    "ref_audio_path": audio_path,
                    "ref_text": ref_text
                }

    return {
        "success": True,
        "emotions": emotions,
        "scanned_count": len(emotions),
        "base_path": str(base)
    }


@router.get("/api/admin/debug-info")
async def get_debug_info(user: dict = Depends(get_admin_user)):
    last_debug_info = get_last_debug_info()

    if last_debug_info is None:
        return {
            "success": True,
            "debug_info": None,
            "message": "暂无调试信息，请先进行一次对话"
        }

    return {
        "success": True,
        "debug_info": sanitize_debug_info(last_debug_info)
    }


@router.get("/api/admin/settings")
async def get_admin_settings(admin: dict = Depends(get_admin_user)):
    from database import get_db, get_settings
    import config as app_config
    db = get_db()
    saved = get_settings(db)
    return {
        "success": True,
        "settings": {
            "securityFilterEnabled": saved.get("securityFilterEnabled", security_filter.enabled),
            "proxyEnabled": saved.get("proxyEnabled", False),
            "proxyUrl": saved.get("proxyUrl", ""),
            "verboseLogging": saved.get("verboseLogging", False),
            "autoWeakWriteEnabled": saved.get("autoWeakWriteEnabled", getattr(app_config, "AUTO_WEAK_WRITE_ENABLED", False)),
        }
    }


@router.put("/api/admin/settings")
async def update_admin_settings(settings: dict, admin: dict = Depends(get_admin_user)):
    from database import get_db, save_settings
    if "securityFilterEnabled" in settings:
        security_filter.enabled = settings["securityFilterEnabled"]

    db = get_db()
    save_settings(db, settings)

    return {
        "success": True,
        "message": "设置已保存",
        "settings": {
            "securityFilterEnabled": security_filter.enabled,
            "proxyEnabled": settings.get("proxyEnabled", False),
            "proxyUrl": settings.get("proxyUrl", ""),
            "verboseLogging": settings.get("verboseLogging", False),
            "autoWeakWriteEnabled": settings.get("autoWeakWriteEnabled", False),
        }
    }


@router.post("/api/config/reload")
async def reload_config(user: dict = Depends(get_admin_user)):
    manager = get_config_manager()
    reloaded = manager.check_and_reload()

    return {
        "success": True,
        "reloaded": reloaded,
        "message": "配置已重新加载" if reloaded else "配置无变化",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/api/config/status")
async def get_config_status(user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    status = manager.get_file_status()

    return {
        "success": True,
        "status": {
            "config_path": status["config_path"],
            "exists": status["exists"],
            "last_modified": status["last_modified"],
            "last_modified_str": datetime.fromtimestamp(status["last_modified"]).isoformat() if status["last_modified"] else None,
            "auto_reload": status["auto_reload"],
            "watcher_active": status["watcher_active"],
            "character_count": status["character_count"],
            "check_interval": CONFIG_CHECK_INTERVAL,
        }
    }
