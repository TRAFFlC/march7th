"""
个人配置文件 - 项目迁移时请修改 .env 文件
Personal Configuration File - Please modify .env when migrating
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_dotenv_path = Path(__file__).parent / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_jwt_secret(secret: str) -> str:
    weak_values = {
        "",
        "your-secret-key-here",
        "your_jwt_secret_here",
        "march7th_secret_key_2024",
        "march7th_jwt_secret_key_2024_very_secure",
        "secret",
        "changeme",
    }
    if secret in weak_values or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET 未配置或过弱。请在 .env 中设置至少 32 位的强随机字符串。"
        )
    return secret


MYSQL_CONFIG = {
    "host": _env("MYSQL_HOST", "localhost"),
    "port": int(_env("MYSQL_PORT", "3306")),
    "user": _env("MYSQL_USER", "root"),
    "password": _env("MYSQL_PASSWORD", ""),
    "database": _env("MYSQL_DATABASE", "march7th_chat"),
    "charset": "utf8mb4",
}

OLLAMA_CONFIG = {
    "default_model": _env("LLM_MODEL", "deepseek-r1:8b"),
    "alternative_models": ["qwen3.5:9b"],
    "base_url": "http://localhost:11434",
}

TTS_CONFIG = {
    "default_port": int(_env("TTS_PORT", "9880")),
    "default_version": _env("TTS_VERSION", "v2ProPlus"),
    "ref_audio_text": _env("REF_AUDIO_TEXT", ""),
}

RAG_CONFIG = {
    "embedding_model": _env("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
    "rerank_model": _env("RERANK_MODEL", "BAAI/bge-reranker-base"),
}

ADMIN_CONFIG = {
    "default_username": _env("ADMIN_USERNAME", "admin"),
    "default_password": _env("ADMIN_PASSWORD", ""),
}

LOG_CONFIG = {
    "log_dir": "logs",
    "log_file": "app.log",
    "log_level": "INFO",
}

JWT_SECRET = _validate_jwt_secret(_env("JWT_SECRET", ""))

JWT_CONFIG = {
    "secret": JWT_SECRET,
    "expire_hours": int(_env("JWT_EXPIRE_HOURS", "24")),
}

FRONTEND_CONFIG = {
    "vue_dev_server_port": 5173,
    "api_base_url": "http://127.0.0.1:8000",
}

PATH_CONFIG = {
    "gpt_sovits_dir": _env("GPT_SOVITS_DIR", ""),
    "tts_gpt_weight": _env("TTS_GPT_WEIGHT", ""),
    "tts_sovits_weight": _env("TTS_SOVITS_WEIGHT", ""),
    "ref_audio_path": _env("REF_AUDIO_PATH", ""),
    "images_dir": _env("IMAGES_DIR", ""),
    "ollama_path": _env("OLLAMA_PATH", ""),
}

LLM_MODEL = _env("LLM_MODEL", "deepseek-r1:8b")
LLM_MAX_TOKENS = int(_env("LLM_MAX_TOKENS", "1024"))

OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY", "")
CHATANYWHERE_API_KEY = _env("CHATANYWHERE_API_KEY", "")

_is_production = _env("MARCH7TH_ENV", "development") == "production"
_default_cors_origins = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8000,http://127.0.0.1:8000"
    if not _is_production
    else "http://localhost:7860"
)
CORS_ALLOWED_ORIGINS = [
    origin for origin in _parse_csv_env(_env("CORS_ALLOWED_ORIGINS", _default_cors_origins))
    if origin != "*"
]
