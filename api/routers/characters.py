"""
角色管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from config import LLM_MODEL
from ..deps import (
    get_config_manager,
    get_current_user,
    get_admin_user,
    resolve_safe_path,
    DEFAULT_AVATAR,
    RESOURCES_DIR,
)
from ..schemas import CharacterCreate, UserCharacterUpdate, APIConfigRequest

router = APIRouter()


@router.get("/api/avatar/{character_id}")
async def get_character_avatar(character_id: str):
    manager = get_config_manager()
    char = manager.get_character(character_id)

    default_avatar = DEFAULT_AVATAR

    if not char or not char.avatar_path:
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Avatar not found")

    try:
        avatar_path = resolve_safe_path(char.avatar_path, RESOURCES_DIR)
    except HTTPException:
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Avatar not found")

    if not avatar_path.exists():
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Avatar file not found")

    suffix = avatar_path.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(suffix, 'application/octet-stream')

    return FileResponse(avatar_path, media_type=media_type)


@router.get("/api/template/avatar/{template_id}")
async def get_template_avatar(template_id: str):
    from character_templates import get_template

    template = get_template(template_id)
    default_avatar = DEFAULT_AVATAR

    if not template or not template.get("avatar_path"):
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(
            status_code=404, detail="Template avatar not found")

    try:
        avatar_path = resolve_safe_path(template["avatar_path"], RESOURCES_DIR)
    except HTTPException:
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(
            status_code=404, detail="Template avatar file not found")

    if not avatar_path.exists():
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(
            status_code=404, detail="Template avatar file not found")

    suffix = avatar_path.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(suffix, 'application/octet-stream')

    return FileResponse(avatar_path, media_type=media_type)


@router.get("/api/characters")
async def get_characters(user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    characters = manager.get_all_characters()

    result = []
    for char in characters:
        result.append({
            "id": char.id,
            "name": char.name,
            "avatar_path": char.avatar_path,
            "wake_word": char.wake_word or char.name,
            "llm_model": char.llm_config.model,
            "rag_enabled": char.rag_config.enabled,
            "source": "admin",
            "username": "admin",
            "llm_config": {
                "model": char.llm_config.model,
                "system_prompt": char.llm_config.system_prompt,
                "temperature": char.llm_config.temperature,
                "top_p": char.llm_config.top_p,
                "max_tokens": char.llm_config.max_tokens,
            },
            "rag_config": {
                "collection_name": char.rag_config.collection_name,
                "enabled": char.rag_config.enabled,
                "top_k": char.rag_config.top_k,
                "distance_threshold": char.rag_config.distance_threshold,
                "use_rerank": char.rag_config.use_rerank,
            },
            "api_config": {
                "provider_type": char.api_config.provider_type,
                "base_url": char.api_config.base_url,
                "api_key": ("*" * 8 + char.api_config.api_key[-4:]) if char.api_config.api_key and len(char.api_config.api_key) > 4 else ("*" * 8 if char.api_config.api_key else ""),
                "has_api_key": bool(char.api_config.api_key),
                "model_name": char.api_config.model_name,
            },
            "tts_config": {
                "gpt_weight": char.tts_config.gpt_weight,
                "sovits_weight": char.tts_config.sovits_weight,
                "ref_audio_path": char.tts_config.ref_audio_path,
                "ref_audio_text": char.tts_config.ref_audio_text,
                "port": char.tts_config.port,
                "version": char.tts_config.version,
            },
            "persona_config": {
                "file": char.persona_config.file,
                "db_dir": char.persona_config.db_dir,
                "min_rating": char.persona_config.min_rating,
                "top_k": char.persona_config.top_k,
            },
            "memory_config": {
                "history_limit": char.memory_config.history_limit,
                "max_context_tokens": char.memory_config.max_context_tokens,
                "output_reserved": char.memory_config.output_reserved,
                "min_output_tokens": char.memory_config.min_output_tokens,
            },
            "iteration_api_config": {
                "provider_type": char.iteration_api_config.provider_type,
                "base_url": char.iteration_api_config.base_url,
                "api_key": ("*" * 8 + char.iteration_api_config.api_key[-4:]) if char.iteration_api_config.api_key and len(char.iteration_api_config.api_key) > 4 else ("*" * 8 if char.iteration_api_config.api_key else ""),
                "has_api_key": bool(char.iteration_api_config.api_key),
                "model_name": char.iteration_api_config.model_name,
            } if char.iteration_api_config else None,
            "iteration_apis": [
                {
                    "provider_type": api.get("provider_type", "openai_compatible"),
                    "base_url": api.get("base_url", ""),
                    "api_key": ("*" * 8 + api.get("api_key", "")[-4:]) if api.get("api_key") and len(api.get("api_key", "")) > 4 else ("*" * 8 if api.get("api_key") else ""),
                    "has_api_key": bool(api.get("api_key")),
                    "model_name": api.get("model_name", ""),
                } for api in (char.iteration_apis or [])
            ],
            "emotion_api_config": {
                "provider_type": char.emotion_api_config.provider_type,
                "base_url": char.emotion_api_config.base_url,
                "api_key": ("*" * 8 + char.emotion_api_config.api_key[-4:]) if char.emotion_api_config.api_key and len(char.emotion_api_config.api_key) > 4 else ("*" * 8 if char.emotion_api_config.api_key else ""),
                "has_api_key": bool(char.emotion_api_config.api_key),
                "model_name": char.emotion_api_config.model_name,
            } if char.emotion_api_config else None,
            "greeting_templates": char.greeting_templates,
            "emotions": {k: {"ref_audio_path": v.ref_audio_path, "ref_text": v.ref_text} for k, v in char.emotions.items()},
            "emotion_images": char.emotion_images,
        })

    if user.get("role") == "admin":
        from database import get_db, get_all_user_characters
        db = get_db()
        user_chars = get_all_user_characters(db)
        import json
        for uc in user_chars:
            char_data = json.loads(uc['character_data']) if isinstance(
                uc['character_data'], str) else uc['character_data']
            result.append({
                "id": uc['character_id'],
                "name": char_data.get('name', '未命名'),
                "avatar_path": char_data.get('avatar_path'),
                "wake_word": char_data.get('wake_word', char_data.get('name', '未命名')),
                "llm_model": char_data.get('llm_model'),
                "rag_enabled": char_data.get('rag_enabled', True),
                "source": "user",
                "user_character_id": uc['id'],
                "user_id": uc['user_id'],
                "username": uc.get('username'),
                "created_at": str(uc['created_at']) if uc.get('created_at') else None,
            })
    else:
        from database import get_db, get_user_characters
        db = get_db()
        user_chars = get_user_characters(db, user['user_id'])
        import json
        for uc in user_chars:
            char_data = json.loads(uc['character_data']) if isinstance(
                uc['character_data'], str) else uc['character_data']
            result.append({
                "id": uc['character_id'],
                "name": char_data.get('name', '未命名'),
                "avatar_path": char_data.get('avatar_path'),
                "wake_word": char_data.get('wake_word', char_data.get('name', '未命名')),
                "llm_model": char_data.get('llm_model'),
                "rag_enabled": char_data.get('rag_enabled', True),
                "source": "user",
                "user_character_id": uc['id'],
                "created_at": str(uc['created_at']) if uc.get('created_at') else None,
            })

    return {"success": True, "characters": result}


@router.get("/api/characters/templates")
async def get_character_templates(user: dict = Depends(get_current_user)):
    from character_templates import get_templates_summary

    templates = get_templates_summary()

    return {
        "success": True,
        "templates": templates
    }


@router.post("/api/characters/import/{template_id}")
async def import_character_template(template_id: str, user: dict = Depends(get_current_user)):
    from character_templates import import_template_to_user

    result = import_template_to_user(template_id, user['user_id'])

    if not result:
        raise HTTPException(status_code=400, detail="模板不存在或用户已拥有该角色")

    return {
        "success": True,
        "message": "角色已成功导入",
    }


@router.get("/api/characters/{char_id}")
async def get_character(char_id: str, user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    char = manager.get_character(char_id)

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {
        "success": True,
        "character": {
            "id": char.id,
            "name": char.name,
            "avatar_path": char.avatar_path,
            "llm_model": char.llm_config.model,
            "system_prompt": char.llm_config.system_prompt,
            "temperature": char.llm_config.temperature,
            "top_p": char.llm_config.top_p,
            "rag_enabled": char.rag_config.enabled,
            "rag_collection": char.rag_config.collection_name,
            "wake_word": char.wake_word or char.name,
        }
    }


@router.get("/api/characters/{char_id}/wake-word")
async def get_character_wake_word(char_id: str, user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    char = manager.get_character(char_id)

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    wake_word = char.wake_word or char.name

    return {
        "success": True,
        "character_id": char_id,
        "wake_word": wake_word
    }


@router.post("/api/characters")
async def create_or_update_character(data: CharacterCreate, user: dict = Depends(get_current_user)):
    from character_config import CharacterConfig, LLMConfig, TTSConfig, RAGConfig, APIConfig, EmotionAudioConfig

    manager = get_config_manager()

    llm_config = LLMConfig(
        model=data.llm_model or LLM_MODEL,
        system_prompt=data.system_prompt or "",
        temperature=data.temperature or 1.0,
        top_p=data.top_p or 0.9,
    )

    tts_data = data.tts_config or {}
    if not tts_data and (data.gpt_weight or data.sovits_weight):
        tts_data = {
            "gpt_weight": data.gpt_weight or "",
            "sovits_weight": data.sovits_weight or "",
            "ref_audio_path": data.ref_audio_path or "",
            "ref_audio_text": data.ref_audio_text or "",
        }

    existing = manager.get_character(data.id)

    tts_config = TTSConfig(
        gpt_weight=tts_data.get("gpt_weight", "") or (existing.tts_config.gpt_weight if existing else ""),
        sovits_weight=tts_data.get("sovits_weight", "") or (existing.tts_config.sovits_weight if existing else ""),
        ref_audio_path=tts_data.get("ref_audio_path", "") or (existing.tts_config.ref_audio_path if existing else ""),
        ref_audio_text=tts_data.get("ref_audio_text", "") or (existing.tts_config.ref_audio_text if existing else ""),
        port=tts_data.get("port", 9880) or (existing.tts_config.port if existing else 9880),
        version=tts_data.get("version", "v2ProPlus") or (existing.tts_config.version if existing else "v2ProPlus"),
    )

    rag_config = RAGConfig(
        collection_name=data.rag_collection or "",
        enabled=data.rag_enabled if data.rag_enabled is not None else True,
    )

    emotions_data = data.emotions or {}
    emotions = {}
    if emotions_data:
        for emotion_name, emotion_value in emotions_data.items():
            if isinstance(emotion_value, dict):
                emotions[emotion_name] = EmotionAudioConfig(
                    ref_audio_path=emotion_value.get("ref_audio_path", ""),
                    ref_text=emotion_value.get("ref_text", ""),
                )
    elif existing and existing.emotions:
        emotions = existing.emotions

    api_config = None
    if data.api_config:
        api_key = data.api_config.get("api_key", "")
        if existing and existing.api_config and not api_key:
            api_key = existing.api_config.api_key
        api_config = APIConfig(
            provider_type=data.api_config.get("provider_type", "ollama"),
            base_url=data.api_config.get("base_url", ""),
            api_key=api_key,
            model_name=data.api_config.get("model_name", ""),
        )

    iteration_api_config = None
    if data.iteration_api_config:
        api_key = data.iteration_api_config.get("api_key", "")
        if existing and existing.iteration_api_config and not api_key:
            api_key = existing.iteration_api_config.api_key
        iteration_api_config = APIConfig(
            provider_type=data.iteration_api_config.get(
                "provider_type", "ollama"),
            base_url=data.iteration_api_config.get("base_url", ""),
            api_key=api_key,
            model_name=data.iteration_api_config.get("model_name", ""),
        )

    emotion_api_config = None
    if data.emotion_api_config:
        api_key = data.emotion_api_config.get("api_key", "")
        if existing and existing.emotion_api_config and not api_key:
            api_key = existing.emotion_api_config.api_key
        emotion_api_config = APIConfig(
            provider_type=data.emotion_api_config.get(
                "provider_type", "ollama"),
            base_url=data.emotion_api_config.get("base_url", ""),
            api_key=api_key,
            model_name=data.emotion_api_config.get("model_name", ""),
        )

    character = CharacterConfig(
        id=data.id,
        name=data.name,
        avatar_path=data.avatar_path or "",
        wake_word=data.wake_word or "",
        llm_config=llm_config,
        tts_config=tts_config,
        rag_config=rag_config,
        api_config=api_config,
        iteration_api_config=iteration_api_config,
        iteration_apis=data.iteration_apis if data.iteration_apis else (existing.iteration_apis if existing else []),
        emotion_api_config=emotion_api_config,
        greeting_templates=data.greeting_templates,
        emotions=emotions,
    )

    if existing:
        success = manager.update_character(character)
        action = "更新"
    else:
        success = manager.add_character(character)
        action = "创建"

    if not success:
        raise HTTPException(status_code=400, detail=f"角色{action}失败")

    return {"success": True, "message": f"角色已{action}"}


@router.delete("/api/characters/{char_id}")
async def delete_character(char_id: str, user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    success = manager.delete_character(char_id)

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {"success": True, "message": "角色已删除"}


@router.get("/api/characters/{char_id}/api-config")
async def get_api_config(char_id: str, user: dict = Depends(get_current_user)):
    from character_config import APIConfig

    manager = get_config_manager()
    char = manager.get_character(char_id)

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    api_config = char.api_config
    return {
        "success": True,
        "api_config": {
            "provider_type": api_config.provider_type,
            "base_url": api_config.base_url,
            "api_key": "",
            "model_name": api_config.model_name,
        }
    }


@router.put("/api/characters/{char_id}/api-config")
async def update_api_config(char_id: str, data: APIConfigRequest, user: dict = Depends(get_current_user)):
    from character_config import APIConfig

    manager = get_config_manager()
    char = manager.get_character(char_id)

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    new_api_config = APIConfig(
        provider_type=data.provider_type,
        base_url=data.base_url,
        api_key=data.api_key,
        model_name=data.model_name,
    )

    if data.provider_type == "ollama" and not data.api_key:
        new_api_config.api_key = ""

    char.api_config = new_api_config
    success = manager.update_character(char)

    if not success:
        raise HTTPException(status_code=400, detail="更新API配置失败")

    return {"success": True, "message": "API配置已更新"}


@router.get("/api/characters/my")
async def get_my_characters(user: dict = Depends(get_current_user)):
    from database import get_db, get_user_characters
    import json

    db = get_db()
    user_chars = get_user_characters(db, user['user_id'])

    result = []
    for uc in user_chars:
        char_data = json.loads(uc['character_data']) if isinstance(
            uc['character_data'], str) else uc['character_data']
        result.append({
            "id": uc['id'],
            "character_id": uc['character_id'],
            "name": char_data.get('name', '未命名'),
            "avatar_path": char_data.get('avatar_path'),
            "llm_model": char_data.get('llm_model'),
            "system_prompt": char_data.get('system_prompt'),
            "temperature": char_data.get('temperature', 1.0),
            "top_p": char_data.get('top_p', 0.9),
            "rag_enabled": char_data.get('rag_enabled', True),
            "rag_collection": char_data.get('rag_collection'),
            "created_at": str(uc['created_at']) if uc.get('created_at') else None,
        })

    return {"success": True, "characters": result}


@router.post("/api/characters/my")
async def create_my_character(data: CharacterCreate, user: dict = Depends(get_current_user)):
    from database import get_db, create_user_character

    char_data = {
        "name": data.name,
        "avatar_path": data.avatar_path,
        "llm_model": data.llm_model,
        "system_prompt": data.system_prompt,
        "temperature": data.temperature,
        "top_p": data.top_p,
        "gpt_weight": data.gpt_weight,
        "sovits_weight": data.sovits_weight,
        "ref_audio_path": data.ref_audio_path,
        "ref_audio_text": data.ref_audio_text,
        "rag_collection": data.rag_collection,
        "rag_enabled": data.rag_enabled,
    }

    db = get_db()
    user_char_id = create_user_character(
        db, user['user_id'], data.id, char_data)

    if not user_char_id:
        raise HTTPException(status_code=400, detail="创建角色失败")

    return {"success": True, "message": "角色已创建", "user_character_id": user_char_id}


@router.put("/api/characters/my/{user_character_id}")
async def update_my_character(user_character_id: int, data: UserCharacterUpdate, user: dict = Depends(get_current_user)):
    from database import get_db, update_user_character

    db = get_db()
    success = update_user_character(
        db, user_character_id, data.character_data, user_id=user['user_id'])

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在或无权限")

    return {"success": True, "message": "角色已更新"}


@router.delete("/api/characters/my/{user_character_id}")
async def delete_my_character(user_character_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, delete_user_character

    db = get_db()
    success = delete_user_character(
        db, user_character_id, user_id=user['user_id'])

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在或无权限")

    return {"success": True, "message": "角色已删除"}
