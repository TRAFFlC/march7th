"""
提示词管理模块
统一管理所有系统提示词的加载、缓存和格式化
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


PROMPTS_DIR = Path(__file__).parent / "config" / "prompts"


class PromptManager:
    _instance: Optional["PromptManager"] = None

    def __new__(cls, prompts_dir: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, prompts_dir: Optional[Path] = None):
        if self._initialized:
            return
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._cache: Dict[str, Dict[str, str]] = {}
        self._initialized = True

    def _load_template(self, name: str) -> Dict[str, str]:
        if name in self._cache:
            return self._cache[name]

        file_path = self.prompts_dir / f"{name}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._cache[name] = data
        return data

    def get_prompt(self, name: str, key: str, **kwargs) -> str:
        template_data = self._load_template(name)
        template = template_data.get(key, "")
        if not template:
            raise KeyError(f"提示词 '{name}.{key}' 不存在")
        if kwargs:
            return template.format(**kwargs)
        return template

    def get_raw_prompt(self, name: str, key: str) -> str:
        template_data = self._load_template(name)
        return template_data.get(key, "")

    def reload(self, name: Optional[str] = None):
        if name:
            self._cache.pop(name, None)
        else:
            self._cache.clear()


_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
