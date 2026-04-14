"""
角色配置管理模块
提供角色卡片配置的加载、保存、增删改查功能
支持配置文件热重载
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
import copy

from llm_provider import APIConfig as _APIConfig


BASE_DIR = Path(__file__).parent
CHARACTERS_CONFIG_PATH = BASE_DIR / "config" / "characters.json"

from config import GPT_SOVITS_DIR


def resolve_tts_path(path: str) -> str:
    if not path:
        return path
    p = Path(path)
    if p.is_absolute():
        return str(p)
    if path.startswith("resources/"):
        return str(BASE_DIR / path)
    return str(Path(GPT_SOVITS_DIR) / path)


def resolve_avatar_path(path: str) -> str:
    if not path:
        return path
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str(BASE_DIR / path)


@dataclass
class LLMConfig:
    model: str = "deepseek-r1:8b"
    system_prompt: str = ""
    temperature: float = 1.0
    top_p: float = 0.9
    max_tokens: int = 1024


@dataclass
class TTSConfig:
    gpt_weight: str = ""
    sovits_weight: str = ""
    ref_audio_path: str = ""
    ref_audio_text: str = ""
    port: int = 9880
    version: str = "v2ProPlus"


@dataclass
class RAGConfig:
    collection_name: str = ""
    enabled: bool = True
    top_k: int = 3
    distance_threshold: float = 1.0
    use_rerank: bool = False


@dataclass
class PersonaConfig:
    file: str = "user_persona.jsonl"
    db_dir: str = "persona_db"
    min_rating: int = 4
    top_k: int = 2


@dataclass
class MemoryConfig:
    history_limit: int = 50
    max_context_tokens: int = 16384
    output_reserved: int = 500
    min_output_tokens: int = 100


@dataclass
class APIConfig:
    provider_type: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""


@dataclass
class EmotionAudioConfig:
    ref_audio_path: str = ""
    ref_text: str = ""

    def is_valid(self) -> bool:
        return bool(self.ref_audio_path and self.ref_text)


@dataclass
class CharacterConfig:
    id: str
    name: str
    avatar_path: str = ""
    wake_word: str = ""
    llm_config: LLMConfig = field(default_factory=LLMConfig)
    tts_config: TTSConfig = field(default_factory=TTSConfig)
    rag_config: RAGConfig = field(default_factory=RAGConfig)
    persona_config: PersonaConfig = field(default_factory=PersonaConfig)
    memory_config: MemoryConfig = field(default_factory=MemoryConfig)
    api_config: APIConfig = field(default_factory=APIConfig)
    iteration_api_config: Optional[APIConfig] = None
    emotion_api_config: Optional[APIConfig] = None
    emotion_images: Dict[str, str] = field(default_factory=lambda: {
        "neutral": "", "happy": "", "confused": "", "sad": "", "angry": "", "excited": ""
    })
    emotions: Dict[str, EmotionAudioConfig] = field(default_factory=dict)
    greeting_templates: Dict[str, str] = field(default_factory=lambda: {
        "morning": "", "afternoon": "", "evening": "", "night": ""
    })

    def to_dict(self) -> Dict[str, Any]:
        emotions_dict = {}
        for emotion_name, emotion_config in self.emotions.items():
            emotions_dict[emotion_name] = {
                "ref_audio_path": emotion_config.ref_audio_path,
                "ref_text": emotion_config.ref_text,
            }
        result = {
            "id": self.id,
            "name": self.name,
            "avatar_path": self.avatar_path,
            "wake_word": self.wake_word,
            "llm_config": asdict(self.llm_config),
            "tts_config": asdict(self.tts_config),
            "rag_config": asdict(self.rag_config),
            "persona_config": asdict(self.persona_config),
            "memory_config": asdict(self.memory_config),
            "api_config": asdict(self.api_config),
            "iteration_api_config": asdict(self.iteration_api_config) if self.iteration_api_config else None,
            "emotion_api_config": asdict(self.emotion_api_config) if self.emotion_api_config else None,
            "emotion_images": self.emotion_images,
            "emotions": emotions_dict,
            "greeting_templates": self.greeting_templates,
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterConfig":
        llm_data = data.get("llm_config", {})
        tts_data = data.get("tts_config", {})
        rag_data = data.get("rag_config", {})
        persona_data = data.get("persona_config", {})
        memory_data = data.get("memory_config", {})
        api_data = data.get("api_config", {})
        iteration_api_data = data.get("iteration_api_config")
        emotion_api_data = data.get("emotion_api_config")

        tts_data_resolved = {
            "gpt_weight": resolve_tts_path(tts_data.get("gpt_weight", "")),
            "sovits_weight": resolve_tts_path(tts_data.get("sovits_weight", "")),
            "ref_audio_path": resolve_tts_path(tts_data.get("ref_audio_path", "")),
            "ref_audio_text": tts_data.get("ref_audio_text", ""),
            "port": tts_data.get("port", 9880),
            "version": tts_data.get("version", "v2ProPlus"),
        }

        emotions_data = data.get("emotions", {})
        if not emotions_data:
            emotions_data = data.get("emotion_images", {})

        emotions_resolved: Dict[str, EmotionAudioConfig] = {}
        for emotion_name, emotion_value in emotions_data.items():
            if isinstance(emotion_value, dict):
                emotions_resolved[emotion_name] = EmotionAudioConfig(
                    ref_audio_path=resolve_tts_path(emotion_value.get("ref_audio_path", "")),
                    ref_text=emotion_value.get("ref_text", ""),
                )

        iteration_api_config = None
        if iteration_api_data and isinstance(iteration_api_data, dict):
            _iter_api_key = iteration_api_data.get("api_key", "")
            if not _iter_api_key:
                from personal_config import OPENROUTER_API_KEY
                if OPENROUTER_API_KEY and iteration_api_data.get("base_url", "").startswith("https://openrouter.ai"):
                    iteration_api_data = dict(iteration_api_data, api_key=OPENROUTER_API_KEY)
            iteration_api_config = APIConfig(**iteration_api_data)

        emotion_api_config = None
        if emotion_api_data and isinstance(emotion_api_data, dict):
            emotion_api_config = APIConfig(**emotion_api_data)

        return cls(
            id=data["id"],
            name=data["name"],
            avatar_path=resolve_avatar_path(data.get("avatar_path", "")),
            wake_word=data.get("wake_word", ""),
            llm_config=LLMConfig(**llm_data),
            tts_config=TTSConfig(**tts_data_resolved),
            rag_config=RAGConfig(**rag_data),
            persona_config=PersonaConfig(**persona_data),
            memory_config=MemoryConfig(**memory_data),
            api_config=APIConfig(**api_data),
            iteration_api_config=iteration_api_config,
            emotion_api_config=emotion_api_config,
            emotions=emotions_resolved,
            emotion_images=data.get("emotion_images", {
                "neutral": "", "happy": "", "confused": "", "sad": "", "angry": "", "excited": ""
            }),
            greeting_templates=data.get("greeting_templates", {
                "morning": "", "afternoon": "", "evening": "", "night": ""
            }),
        )


class CharacterConfigManager:
    """
    角色配置管理器
    提供角色配置的加载、保存、增删改查功能
    支持配置文件热重载
    """

    _instance: Optional["CharacterConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls, config_path: Optional[Path] = None, auto_reload: bool = True):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, config_path: Optional[Path] = None, auto_reload: bool = True):
        if getattr(self, '_initialized', False):
            return

        self.config_path = config_path or CHARACTERS_CONFIG_PATH
        self._characters: Dict[str, CharacterConfig] = {}
        self._file_mtime: float = 0.0
        self._auto_reload = auto_reload
        self._watcher_thread: Optional[threading.Thread] = None
        self._stop_watcher = threading.Event()
        self._reload_callbacks: List[callable] = []
        self._load()
        self._update_mtime()
        self._initialized = True

    def _update_mtime(self) -> None:
        if self.config_path.exists():
            self._file_mtime = self.config_path.stat().st_mtime

    def _load(self) -> None:
        if not self.config_path.exists():
            self._characters = {}
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        characters_data = data.get("characters", [])
        for char_data in characters_data:
            char = CharacterConfig.from_dict(char_data)
            self._characters[char.id] = char

    def _save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "characters": [char.to_dict() for char in self._characters.values()]
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._update_mtime()

    def needs_reload(self) -> bool:
        if not self.config_path.exists():
            return False
        current_mtime = self.config_path.stat().st_mtime
        return current_mtime > self._file_mtime

    def check_and_reload(self) -> bool:
        if self.needs_reload():
            self.reload()
            self._notify_reload_callbacks()
            return True
        return False

    def add_reload_callback(self, callback: callable) -> None:
        self._reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: callable) -> None:
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)

    def _notify_reload_callbacks(self) -> None:
        for callback in self._reload_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"[ConfigManager] 回调执行失败: {e}")

    def start_file_watcher(self, interval: int = 30) -> None:
        if self._watcher_thread and self._watcher_thread.is_alive():
            return

        self._stop_watcher.clear()

        def _watch():
            while not self._stop_watcher.wait(interval):
                try:
                    self.check_and_reload()
                except Exception as e:
                    print(f"[ConfigManager] 文件监控错误: {e}")

        self._watcher_thread = threading.Thread(target=_watch, daemon=True)
        self._watcher_thread.start()

    def stop_file_watcher(self) -> None:
        self._stop_watcher.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5)
            self._watcher_thread = None

    def get_file_status(self) -> Dict[str, Any]:
        return {
            "config_path": str(self.config_path),
            "exists": self.config_path.exists(),
            "last_modified": self._file_mtime,
            "auto_reload": self._auto_reload,
            "watcher_active": self._watcher_thread.is_alive() if self._watcher_thread else False,
            "character_count": len(self._characters),
        }

    def get_character(self, character_id: str) -> Optional[CharacterConfig]:
        char = self._characters.get(character_id)
        if char is None:
            for c in self._characters.values():
                if c.name == character_id:
                    return c
        return char

    def get_all_characters(self) -> List[CharacterConfig]:
        return list(self._characters.values())

    def get_character_ids(self) -> List[str]:
        return list(self._characters.keys())

    def add_character(self, character: CharacterConfig) -> bool:
        if character.id in self._characters:
            return False
        self._characters[character.id] = character
        self._save()
        return True

    def update_character(self, character: CharacterConfig) -> bool:
        if character.id not in self._characters:
            return False
        self._characters[character.id] = character
        self._save()
        return True

    def delete_character(self, character_id: str) -> bool:
        if character_id not in self._characters:
            return False
        del self._characters[character_id]
        self._save()
        return True

    def character_exists(self, character_id: str) -> bool:
        return character_id in self._characters

    def reload(self) -> None:
        self._load()

    def create_character(
        self,
        character_id: str,
        name: str,
        **kwargs
    ) -> CharacterConfig:
        llm_config = LLMConfig(**kwargs.get("llm_config", {}))
        tts_config = TTSConfig(**kwargs.get("tts_config", {}))
        rag_config = RAGConfig(**kwargs.get("rag_config", {}))
        persona_config = PersonaConfig(**kwargs.get("persona_config", {}))
        memory_config = MemoryConfig(**kwargs.get("memory_config", {}))

        character = CharacterConfig(
            id=character_id,
            name=name,
            avatar_path=kwargs.get("avatar_path", ""),
            llm_config=llm_config,
            tts_config=tts_config,
            rag_config=rag_config,
            persona_config=persona_config,
            memory_config=memory_config,
        )
        return character


def get_march7th_config(manager: Optional[CharacterConfigManager] = None) -> Optional[CharacterConfig]:
    if manager is None:
        manager = CharacterConfigManager()
    return manager.get_character("march7th")


def main():
    manager = CharacterConfigManager()

    print("=" * 50)
    print("角色配置管理器测试")
    print("=" * 50)

    print(f"\n配置文件路径: {manager.config_path}")
    print(f"已加载角色数量: {len(manager.get_all_characters())}")

    for char in manager.get_all_characters():
        print(f"\n角色 ID: {char.id}")
        print(f"  名称: {char.name}")
        print(f"  LLM 模型: {char.llm_config.model}")
        print(f"  TTS 版本: {char.tts_config.version}")
        print(f"  RAG 启用: {char.rag_config.enabled}")
        print(f"  RAG 集合: {char.rag_config.collection_name}")

    march7th = manager.get_character("march7th")
    if march7th:
        print(f"\n三月七配置加载成功!")
        print(
            f"  System Prompt 长度: {len(march7th.llm_config.system_prompt)} 字符")


if __name__ == "__main__":
    main()
