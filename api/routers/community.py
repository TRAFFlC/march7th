"""
社区角色市场路由
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from config import LLM_MODEL
from ..deps import get_config_manager, get_current_user, DEFAULT_AVATAR

router = APIRouter()


@router.get("/api/community/characters")
async def get_community_characters(user: dict = Depends(get_current_user)):
    from database import get_db, get_community_characters
    db = get_db()
    characters = get_community_characters(db)

    result = []
    for char in characters:
        char_data = json.loads(char['character_data']) if isinstance(
            char['character_data'], str) else char['character_data']
        result.append({
            "id": char['id'],
            "character_id": char['character_id'],
            "name": char_data.get('name', '未命名'),
            "avatar_path": char_data.get('avatar_path'),
            "llm_model": char_data.get('llm_model', LLM_MODEL),
            "description": char.get('description', ''),
            "download_count": char['download_count'],
            "username": char['username'],
            "user_avatar": char.get('user_avatar'),
            "created_at": str(char['created_at']) if char.get('created_at') else None,
        })

    return {"success": True, "characters": result}


@router.post("/api/community/publish")
async def publish_to_community(request: dict, user: dict = Depends(get_current_user)):
    from database import get_db, publish_character_to_community, is_character_published

    character_id = request.get('character_id')
    description = request.get('description', '')

    if not character_id:
        raise HTTPException(status_code=400, detail="缺少角色ID")

    db = get_db()

    if is_character_published(db, user['user_id'], character_id):
        raise HTTPException(status_code=400, detail="该角色已发布到社区")

    manager = get_config_manager()
    char = manager.get_character(character_id)

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    char_data = {
        "id": char.id,
        "name": char.name,
        "avatar_path": char.avatar_path,
        "wake_word": char.wake_word,
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
        },
        "tts_config": {
            "gpt_weight": char.tts_config.gpt_weight,
            "sovits_weight": char.tts_config.sovits_weight,
            "ref_audio_path": char.tts_config.ref_audio_path,
            "ref_audio_text": char.tts_config.ref_audio_text,
            "port": char.tts_config.port,
            "version": char.tts_config.version,
        },
    }

    result = publish_character_to_community(
        db, user['user_id'], character_id, char_data, description)

    if not result:
        raise HTTPException(status_code=500, detail="发布失败")

    return {"success": True, "message": "角色已发布到社区市场"}


@router.post("/api/community/import/{community_id}")
async def import_from_community(community_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_community_character, increment_download_count
    from character_config import CharacterConfig, LLMConfig, TTSConfig, RAGConfig, PersonaConfig, MemoryConfig, CharacterConfigManager

    db = get_db()
    char = get_community_character(db, community_id)

    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    char_data = json.loads(char['character_data']) if isinstance(
        char['character_data'], str) else char['character_data']

    manager = CharacterConfigManager()
    new_id = f"{char_data['id']}_{user['user_id']}"

    if manager.character_exists(new_id):
        raise HTTPException(status_code=400, detail="您已拥有该角色")

    llm_data = char_data.get('llm_config', {})
    tts_data = char_data.get('tts_config', {})
    rag_data = char_data.get('rag_config', {})

    llm_config = LLMConfig(
        model=llm_data.get('model', LLM_MODEL),
        system_prompt=llm_data.get('system_prompt', ''),
        temperature=llm_data.get('temperature', 1.0),
        top_p=llm_data.get('top_p', 0.9),
        max_tokens=llm_data.get('max_tokens', 1024),
    )

    tts_config = TTSConfig(
        gpt_weight=tts_data.get('gpt_weight', ''),
        sovits_weight=tts_data.get('sovits_weight', ''),
        ref_audio_path=tts_data.get('ref_audio_path', ''),
        ref_audio_text=tts_data.get('ref_audio_text', ''),
        port=tts_data.get('port', 9880),
        version=tts_data.get('version', 'v2ProPlus'),
    )

    rag_config = RAGConfig(
        collection_name=rag_data.get('collection_name', ''),
        enabled=rag_data.get('enabled', True),
        top_k=rag_data.get('top_k', 3),
    )

    persona_config = PersonaConfig()
    memory_config = MemoryConfig()

    character = CharacterConfig(
        id=new_id,
        name=char_data.get('name', ''),
        avatar_path=char_data.get('avatar_path', ''),
        wake_word=char_data.get('wake_word', ''),
        llm_config=llm_config,
        tts_config=tts_config,
        rag_config=rag_config,
        persona_config=persona_config,
        memory_config=memory_config,
    )

    success = manager.add_character(character)

    if not success:
        raise HTTPException(status_code=500, detail="导入失败")

    increment_download_count(db, community_id)

    return {"success": True, "message": "角色已成功导入"}


@router.delete("/api/community/unpublish/{character_id}")
async def unpublish_from_community(character_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, unpublish_character_from_community

    db = get_db()
    success = unpublish_character_from_community(
        db, user['user_id'], character_id)

    if not success:
        raise HTTPException(status_code=404, detail="未找到已发布的角色")

    return {"success": True, "message": "已取消发布"}


@router.get("/api/community/avatar/{community_id}")
async def get_community_avatar(community_id: int):
    from database import get_db, get_community_character

    db = get_db()
    char = get_community_character(db, community_id)
    default_avatar = DEFAULT_AVATAR

    if not char:
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Character not found")

    char_data = json.loads(char['character_data']) if isinstance(
        char['character_data'], str) else char['character_data']
    avatar_path = char_data.get('avatar_path')

    if not avatar_path:
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Avatar not found")

    avatar_path = Path(avatar_path)
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
