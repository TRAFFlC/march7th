from enum import Enum
from typing import Optional, Tuple

from character_config import CharacterConfigManager


class EmotionType(Enum):
    HAPPY = "happy"
    CONFUSED = "confused"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    NEUTRAL = "neutral"


def get_emotion_config(character_id: str, emotion: str):
    emotion_lower = emotion.lower() if emotion else "neutral"

    valid_emotions = [e.value for e in EmotionType]
    if emotion_lower not in valid_emotions:
        return None

    manager = CharacterConfigManager()
    character = manager.get_character(character_id)
    if not character:
        return None

    return character.emotions.get(emotion_lower)


def get_emotion_audio_path(character_id: str, emotion: str) -> Tuple[Optional[str], Optional[str]]:
    config = get_emotion_config(character_id, emotion)
    if config and config.is_valid():
        return config.ref_audio_path, config.ref_text
    return None, None


def reload_emotion_configs() -> None:
    manager = CharacterConfigManager()
    manager.reload()
