"""
TTS 语音合成路由
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user, get_config_manager
from ..schemas import TTSEmotionRequest

router = APIRouter()


@router.get("/api/tts")
async def text_to_speech(text: str, speed: float = 1.0, emotion: str = "neutral", character_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    import base64

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    try:
        controller = get_controller(user_id=user["user_id"])
        audio_bytes = controller.synthesize_audio(
            text.strip(), speed=speed, emotion=emotion, character_id=character_id)

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="语音合成失败")

        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {"success": True, "audio": audio_base64, "emotion": emotion}
    except Exception as e:
        raise HTTPException(status_code=500, detail="语音合成失败")


@router.post("/api/tts/emotion")
async def text_to_speech_emotion(data: TTSEmotionRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    import base64

    if not data.text or not data.text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    try:
        controller = get_controller(user_id=user["user_id"])
        audio_bytes = controller.synthesize_audio(
            data.text.strip(),
            speed=data.speed,
            emotion=data.emotion,
            character_id=data.character_id,
        )

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="情感语音合成失败")

        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {"success": True, "audio": audio_base64, "emotion": data.emotion}
    except Exception as e:
        raise HTTPException(status_code=500, detail="情感语音合成失败")


@router.get("/api/tts/config")
async def get_tts_config(user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    characters = manager.get_all_characters()
    
    if characters:
        char = characters[0]
        tts_config = char.tts_config
        return {
            "success": True,
            "config": {
                "ref_audio_path": tts_config.ref_audio_path or "",
                "ref_text": tts_config.ref_audio_text or "",
                "gpt_weight": tts_config.gpt_weight or "",
                "sovits_weight": tts_config.sovits_weight or "",
                "port": tts_config.port or 9880,
            }
        }
    
    from tts_service import get_current_ref_config
    config = get_current_ref_config()
    
    return {
        "success": True,
        "config": {
            "ref_audio_path": config.get("ref_audio_path", ""),
            "ref_text": config.get("ref_text", ""),
            "gpt_weight": config.get("gpt_weight", ""),
            "sovits_weight": config.get("sovits_weight", ""),
            "port": config.get("port", 9880),
        }
    }


@router.get("/api/tts/emotion-config")
async def get_tts_emotion_config(character_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    manager = get_config_manager()

    if not character_id:
        characters = manager.get_all_characters()
        if characters:
            character_id = characters[0].id
        else:
            return {
                "success": False,
                "character_id": None,
                "character_name": None,
                "emotions": {}
            }

    character = manager.get_character(character_id)
    if not character:
        return {
            "success": False,
            "character_id": character_id,
            "character_name": None,
            "emotions": {}
        }

    emotions_config = {}
    for emotion_name, emotion_config in character.emotions.items():
        emotions_config[emotion_name] = {
            "ref_audio_path": emotion_config.ref_audio_path,
            "ref_text": emotion_config.ref_text,
        }

    return {
        "success": True,
        "character_id": character_id,
        "character_name": character.name,
        "emotions": emotions_config
    }
