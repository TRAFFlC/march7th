"""
共享依赖与工具函数：常量、JWT 认证、路径安全、配置管理、共享令牌、调试信息
"""
import json
import logging
import time
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import CONFIG_AUTO_RELOAD, CONFIG_CHECK_INTERVAL
from personal_config import JWT_CONFIG
from rate_limiter import rate_limiter, get_client_ip
from security_filter import SecurityFilter

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_AVATAR = BASE_DIR / "frontend" / "public" / "emojis" / "三月七_开心.png"
RESOURCES_DIR = BASE_DIR / "resources"
EMOTIONS_DIR = RESOURCES_DIR / "emotions"
SHARED_TOKEN_FILE = BASE_DIR / "shared_token.json"
SHARED_TOKEN_TTL_SECONDS = 300
MAX_CHAT_HISTORY_LIMIT = 200
MAX_ADMIN_CONVERSATIONS_LIMIT = 500
MAX_SESSIONS_LIMIT = 100

security = HTTPBearer()

JWT_SECRET = JWT_CONFIG.get("secret", "march7th_secret_key_2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = JWT_CONFIG.get("expire_hours", 24)

_security_filter = SecurityFilter(enabled=True)
_config_manager = None
_last_debug_info = None


def _safe_relative_to(path: Path, base_dir: Path) -> bool:
    try:
        path.relative_to(base_dir)
        return True
    except ValueError:
        return False


def resolve_safe_path(path_value: str, allowed_root: Path) -> Path:
    if ".." in path_value.replace("\\", "/").split("/"):
        raise HTTPException(status_code=403, detail="非法路径")
    resolved = Path(path_value).expanduser().resolve()
    allowed_root = allowed_root.resolve()
    if not _safe_relative_to(resolved, allowed_root):
        raise HTTPException(status_code=403, detail="禁止访问资源目录之外的路径")
    return resolved


def build_file_response(file_path: Path, default_path: Path = DEFAULT_AVATAR):
    if not file_path.exists() or not file_path.is_file():
        if default_path.exists():
            return FileResponse(default_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="资源不存在")

    suffix = file_path.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(suffix, 'application/octet-stream')
    return FileResponse(file_path, media_type=media_type)


def ensure_password_complexity(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少8个字符")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=400, detail="密码必须同时包含字母和数字")


def write_shared_token(payload: dict) -> None:
    SHARED_TOKEN_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def read_shared_token_payload() -> dict:
    if not SHARED_TOKEN_FILE.exists():
        raise HTTPException(status_code=404, detail="共享令牌不存在")
    try:
        payload = json.loads(SHARED_TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取共享令牌失败: %s", exc)
        raise HTTPException(status_code=404, detail="共享令牌不可用") from exc

    created_at = payload.get("created_at")
    if not isinstance(created_at, (int, float)):
        try:
            SHARED_TOKEN_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=404, detail="共享令牌已失效")

    if time.time() - created_at > SHARED_TOKEN_TTL_SECONDS:
        try:
            SHARED_TOKEN_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=404, detail="共享令牌已过期")
    return payload


def sanitize_debug_info(debug_info: dict) -> dict:
    if not isinstance(debug_info, dict):
        return {}
    redacted_fields = {"full_prompt", "raw_output", "messages"}
    sanitized = {}
    for key, value in debug_info.items():
        if key in redacted_fields:
            continue
        sanitized[key] = value
    return sanitized


def ensure_conversation_access(conv: Optional[dict], user: dict, not_found_detail: str) -> dict:
    if not conv:
        raise HTTPException(status_code=404, detail=not_found_detail)
    if conv.get("user_id") != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问该对话")
    return conv


def get_config_manager():
    global _config_manager
    if _config_manager is None:
        from character_config import CharacterConfigManager
        _config_manager = CharacterConfigManager(
            auto_reload=CONFIG_AUTO_RELOAD)
    return _config_manager


def set_config_manager(manager) -> None:
    global _config_manager
    _config_manager = manager


def set_last_debug_info(debug_info) -> None:
    global _last_debug_info
    _last_debug_info = debug_info


def get_last_debug_info():
    return _last_debug_info


def create_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
        )
    return payload


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


def export_to_markdown(conversation: dict) -> str:
    rating_map = {1: '⭐', 2: '⭐⭐', 3: '⭐⭐⭐', 4: '⭐⭐⭐⭐', 5: '⭐⭐⭐⭐⭐'}
    rating_stars = rating_map.get(conversation.get('rating', 0), '-')

    lines = [
        "# 对话记录",
        "",
        f"**角色**: {conversation.get('character', '未知')}",
        f"**日期**: {conversation.get('timestamp', '未知')}",
        f"**评分**: {rating_stars}",
        "",
        "## 用户",
        conversation.get('user_input', ''),
        "",
        "## 三月七",
        conversation.get('bot_reply', ''),
    ]

    return '\n'.join(lines)


def export_to_json(conversation: dict) -> dict:
    return {
        "id": conversation.get('id'),
        "character": conversation.get('character'),
        "user_input": conversation.get('user_input'),
        "bot_reply": conversation.get('bot_reply'),
        "rating": conversation.get('rating'),
        "timestamp": str(conversation.get('timestamp', '')),
    }
