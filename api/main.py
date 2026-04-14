"""
FastAPI 后端 API
"""

from config import CONFIG_AUTO_RELOAD, CONFIG_CHECK_INTERVAL, LLM_MODEL
import asyncio
import base64
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, AsyncGenerator
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import jwt
import uvicorn
import subprocess
import requests
import time
import sys
import os
from pathlib import Path
import shutil
from urllib.parse import quote

from personal_config import MYSQL_CONFIG, JWT_CONFIG, PATH_CONFIG
from security_filter import SecurityFilter

OLLAMA_PROCESS = None
_LAST_DEBUG_INFO = None
_config_manager = None
_security_filter = SecurityFilter(enabled=True)


def is_ollama_running() -> bool:
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def start_ollama_serve():
    global OLLAMA_PROCESS

    if is_ollama_running():
        print("[OK] Ollama 已在运行中")
        return True

    print("[INFO] 正在启动 Ollama 服务...")

    try:
        ollama_path = None
        import shutil
        ollama_path = shutil.which("ollama")

        if not ollama_path:
            possible_paths = [
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Ollama\ollama.exe"),
            ]
            _configured_path = PATH_CONFIG.get("ollama_path", "")
            if _configured_path:
                possible_paths.insert(0, _configured_path)
            for path in possible_paths:
                if os.path.exists(path):
                    ollama_path = path
                    break

        if not ollama_path:
            print("[ERROR] 未找到 ollama，请确保已安装 Ollama")
            return False

        print(f"[INFO] 找到 Ollama: {ollama_path}")

        if sys.platform == "win32":
            import subprocess
            subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            )
        else:
            OLLAMA_PROCESS = subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        for i in range(30):
            time.sleep(1)
            if is_ollama_running():
                print("[OK] Ollama 服务已启动")
                return True
            print(f"[INFO] 等待 Ollama 启动... ({i+1}/30)")

        print("[WARN] Ollama 启动超时，请手动启动")
        return False

    except FileNotFoundError:
        print("[ERROR] 未找到 ollama 命令，请确保已安装 Ollama")
        return False
    except Exception as e:
        print(f"[ERROR] 启动 Ollama 失败: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config_manager
    from character_config import CharacterConfigManager

    start_ollama_serve()

    _config_manager = CharacterConfigManager(auto_reload=CONFIG_AUTO_RELOAD)

    if CONFIG_AUTO_RELOAD:
        _config_manager.start_file_watcher(interval=CONFIG_CHECK_INTERVAL)
        print(f"[Config] 自动重载已启用，检查间隔: {CONFIG_CHECK_INTERVAL}秒")

    yield

    if _config_manager:
        _config_manager.stop_file_watcher()
        print("[Config] 文件监控已停止")


app = FastAPI(
    title="三月七语音对话系统 API",
    description="基于 FastAPI 的后端 API",
    version="2.0.0",
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' ws: wss:"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

_cors_origins = getattr(__import__('personal_config'),
                        'CORS_ALLOWED_ORIGINS', None) or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGES_DIR = PATH_CONFIG.get("images_dir", "")
if IMAGES_DIR and os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
    print(f"[OK] 静态图片目录已挂载: {IMAGES_DIR}")


@app.get("/api/avatar/{character_id}")
async def get_character_avatar(character_id: str):
    manager = get_config_manager()
    char = manager.get_character(character_id)
    
    default_avatar = Path(__file__).parent / "frontend" / "public" / "emojis" / "三月七_开心.png"
    
    if not char or not char.avatar_path:
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Avatar not found")
    
    avatar_path = Path(char.avatar_path)
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


@app.get("/api/template/avatar/{template_id}")
async def get_template_avatar(template_id: str):
    from character_templates import get_template
    
    template = get_template(template_id)
    default_avatar = Path(__file__).parent / "frontend" / "public" / "emojis" / "三月七_开心.png"
    
    if not template or not template.get("avatar_path"):
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Template avatar not found")
    
    avatar_path = Path(template["avatar_path"])
    if not avatar_path.exists():
        if default_avatar.exists():
            return FileResponse(default_avatar, media_type="image/png")
        raise HTTPException(status_code=404, detail="Template avatar file not found")
    
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


security = HTTPBearer()

JWT_SECRET = JWT_CONFIG.get("secret", "march7th_secret_key_2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = JWT_CONFIG.get("expire_hours", 24)


def get_config_manager():
    global _config_manager
    if _config_manager is None:
        from character_config import CharacterConfigManager
        _config_manager = CharacterConfigManager(
            auto_reload=CONFIG_AUTO_RELOAD)
    return _config_manager


class UserLogin(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    character_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 0.9
    emotion: Optional[str] = "neutral"
    session_id: Optional[str] = None


class VoiceInputRequest(BaseModel):
    message: str
    character_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 0.9
    emotion: Optional[str] = "neutral"
    session_id: Optional[str] = None


class RatingRequest(BaseModel):
    conversation_id: int
    rating: int


class FeedbackDetailRequest(BaseModel):
    conversation_id: int
    feedback_type: str
    context_snapshot: Optional[dict] = None


class RAGIterationRequest(BaseModel):
    conversation_id: int

    feedback_type: str


class RAGConfirmRequest(BaseModel):
    feedback_detail_id: int


class CharacterCreate(BaseModel):
    id: str
    name: str
    avatar_path: Optional[str] = None
    wake_word: Optional[str] = None
    llm_model: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 0.9
    gpt_weight: Optional[str] = None
    sovits_weight: Optional[str] = None
    ref_audio_path: Optional[str] = None
    ref_audio_text: Optional[str] = None
    rag_collection: Optional[str] = None
    rag_enabled: Optional[bool] = True
    api_config: Optional[dict] = None
    iteration_api_config: Optional[dict] = None
    emotion_api_config: Optional[dict] = None
    greeting_templates: Optional[dict] = None


class UserCharacterUpdate(BaseModel):
    character_data: dict


class MemoryAnchorCreate(BaseModel):
    character_id: str
    content: str
    anchor_type: str = "manual"
    importance: float = 0.5


class MemoryAnchorUpdate(BaseModel):
    content: Optional[str] = None
    anchor_type: Optional[str] = None
    importance: Optional[float] = None
    is_active: Optional[bool] = None


class SessionCreate(BaseModel):
    character_id: str
    title: Optional[str] = None


class UserProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


def create_token(user_id: int, username: str, role: str = 'admin') -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
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


async def get_current_user_from_query(token: Optional[str] = None) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证令牌",
        )
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
        )
    return payload


@app.get("/")
async def root():
    return {"message": "三月七语音对话系统 API", "version": "2.0.0"}


@app.post("/api/auth/login")
async def login(data: UserLogin):
    from database import get_db, verify_user

    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    db = get_db()
    user = verify_user(db, data.username, data.password)

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user['id'], user['username'], 'admin')

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "role": "admin",
        }
    }


@app.post("/api/auth/auto-login")
async def auto_login():
    from database import get_db, get_user_by_username
    db = get_db()
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=500, detail="默认用户不存在")
    token = create_token(user['id'], user['username'], 'admin')
    return {
        "success": True,
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "role": "admin",
        }
    }


@app.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"success": True, "user": user}


@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    from database import get_db, get_user_profile_info

    db = get_db()
    profile = get_user_profile_info(db, user['user_id'])

    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "success": True,
        "profile": {
            "id": profile['id'],
            "username": profile['username'],
            "nickname": profile.get('nickname') or profile['username'],
            "avatar": profile.get('avatar'),
            "created_at": str(profile['created_at']) if profile.get('created_at') else None,
        }
    }


@app.put("/api/user/profile")
async def update_user_profile(data: UserProfileUpdate, user: dict = Depends(get_current_user)):
    from database import get_db, update_user_profile_info

    if data.nickname is None and data.avatar is None:
        raise HTTPException(status_code=400, detail="至少需要提供一个字段")

    if data.nickname is not None and len(data.nickname) > 100:
        raise HTTPException(status_code=400, detail="昵称不能超过100个字符")

    if data.avatar is not None and len(data.avatar) > 500:
        raise HTTPException(status_code=400, detail="头像URL不能超过500个字符")

    db = get_db()
    success = update_user_profile_info(
        db, user['user_id'], data.nickname, data.avatar)

    if not success:
        raise HTTPException(status_code=500, detail="更新失败")

    return {"success": True, "message": "个人信息已更新"}


SHARED_TOKEN_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'shared_token.json')


@app.post("/api/auth/share-token")
async def share_token(user: dict = Depends(get_current_user)):
    token = create_token(user['user_id'], user['username'], user['role'])
    data = {
        "token": token,
        "user": user
    }
    with open(SHARED_TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return {"success": True, "message": "Token shared"}


@app.get("/api/auth/shared-token")
async def get_shared_token():
    if not os.path.exists(SHARED_TOKEN_FILE):
        return {"success": False, "message": "No shared token"}

    try:
        with open(SHARED_TOKEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"success": True, "token": data.get("token"), "user": data.get("user")}
    except:
        return {"success": False, "message": "Failed to read shared token"}


@app.delete("/api/auth/shared-token")
async def delete_shared_token(user: dict = Depends(get_current_user)):
    if os.path.exists(SHARED_TOKEN_FILE):
        os.remove(SHARED_TOKEN_FILE)
    return {"success": True, "message": "Shared token deleted"}


@app.get("/api/characters")
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


@app.get("/api/characters/templates")
async def get_character_templates(user: dict = Depends(get_current_user)):
    from character_templates import get_templates_summary

    templates = get_templates_summary()

    return {
        "success": True,
        "templates": templates
    }


@app.post("/api/characters/import/{template_id}")
async def import_character_template(template_id: str, user: dict = Depends(get_current_user)):
    from character_templates import import_template_to_user

    result = import_template_to_user(template_id, user['user_id'])

    if not result:
        raise HTTPException(status_code=400, detail="模板不存在或用户已拥有该角色")

    return {
        "success": True,
        "message": "角色已成功导入",
    }


@app.get("/api/characters/{char_id}")
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


@app.get("/api/characters/{char_id}/wake-word")
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


@app.post("/api/characters")
async def create_or_update_character(data: CharacterCreate, user: dict = Depends(get_current_user)):
    from character_config import CharacterConfig, LLMConfig, TTSConfig, RAGConfig, APIConfig

    manager = get_config_manager()

    llm_config = LLMConfig(
        model=data.llm_model or LLM_MODEL,
        system_prompt=data.system_prompt or "",
        temperature=data.temperature or 1.0,
        top_p=data.top_p or 0.9,
    )

    tts_config = TTSConfig(
        gpt_weight=data.gpt_weight or "",
        sovits_weight=data.sovits_weight or "",
        ref_audio_path=data.ref_audio_path or "",
        ref_audio_text=data.ref_audio_text or "",
    )

    rag_config = RAGConfig(
        collection_name=data.rag_collection or "",
        enabled=data.rag_enabled if data.rag_enabled is not None else True,
    )

    existing = manager.get_character(data.id)

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
            provider_type=data.iteration_api_config.get("provider_type", "ollama"),
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
            provider_type=data.emotion_api_config.get("provider_type", "ollama"),
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
        emotion_api_config=emotion_api_config,
        greeting_templates=data.greeting_templates,
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


@app.delete("/api/characters/{char_id}")
async def delete_character(char_id: str, user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    success = manager.delete_character(char_id)

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {"success": True, "message": "角色已删除"}


@app.post("/api/chat")
async def chat(data: ChatRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from database import get_db, save_conversation, create_session, get_session, update_session

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    is_safe, threats = _security_filter.check(data.message.strip())
    if not is_safe:
        threat_types = list(set(t["type"] for t in threats))
        return {
            "success": False,
            "response": "⚠️ 您的输入触发了安全过滤器，请修改后重试。",
            "conversation_id": None,
            "audio": None,
            "debug": {"security_threats": threat_types},
        }

    try:
        db = get_db()
        session_id = data.session_id
        session = None

        if session_id:
            session = get_session(db, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")
            if session['user_id'] != user['user_id']:
                raise HTTPException(status_code=403, detail="无权访问该会话")

        controller = get_controller(character_id=data.character_id)

        if not session_id:
            actual_character_id = data.character_id or controller.get_current_character_id()
            if actual_character_id:
                session_id = create_session(
                    db, user['user_id'], actual_character_id)

        if session_id and session:
            controller.switch_session(session_id, user['user_id'])

        response_text, audio_bytes, conversation_id, debug_info = controller.process_user_input(
            data.message.strip(),
            character_id=data.character_id,
            model_name=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            user_id=user['user_id'],
            emotion=data.emotion,
            session_id=session_id,
        )

        audio_base64 = None
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        if session_id:
            session = get_session(db, session_id)
            update_session(db, session_id,
                           last_message_at=datetime.utcnow(),
                           message_count=session.get('message_count', 0) + 1 if session else 1)

        global _LAST_DEBUG_INFO
        _LAST_DEBUG_INFO = debug_info

        return {
            "success": True,
            "response": response_text,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "audio": audio_base64,
            "debug": {
                "llm_time": debug_info.get("llm", {}).get("generation_time", 0),
                "tts_time": debug_info.get("tts", {}).get("synthesis_time", 0),
                "total_time": debug_info.get("total_time", 0),
            }
        }
    except Exception as e:
        if 'debug_info' in locals():
            _LAST_DEBUG_INFO = debug_info
        raise HTTPException(status_code=500, detail="处理对话时发生内部错误")


@app.post("/api/voice/input")
async def voice_input(data: VoiceInputRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from database import get_db, save_conversation, create_session, get_session, update_session

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    is_safe, threats = _security_filter.check(data.message.strip())
    if not is_safe:
        threat_types = list(set(t["type"] for t in threats))
        return {
            "success": False,
            "response": "⚠️ 您的输入触发了安全过滤器，请修改后重试。",
            "conversation_id": None,
            "audio": None,
            "debug": {"security_threats": threat_types},
        }

    try:
        controller = get_controller(character_id=data.character_id)
        db = get_db()
        
        actual_character_id = data.character_id or controller.get_current_character_id()
        session_id = data.session_id
        session = None

        if session_id:
            session = get_session(db, session_id)
            if session and session['user_id'] == user['user_id']:
                print(f"[Voice] 复用已有会话: {session_id}")
            else:
                session = None
                session_id = None

        if not session_id:
            session_id = create_session(db, user['user_id'], actual_character_id, title=data.message.strip()[:50])
            print(f"[Voice] 创建新会话: {session_id}")

        if session_id and session:
            controller.switch_session(session_id, user['user_id'])

        response_text, audio_bytes, conversation_id, debug_info = await asyncio.to_thread(
            controller.process_user_input,
            data.message.strip(),
            character_id=data.character_id,
            model_name=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            user_id=user['user_id'],
            emotion=data.emotion,
            session_id=session_id,
        )

        audio_base64 = None
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        if session_id:
            session = get_session(db, session_id)
            update_session(db, session_id,
                           last_message_at=datetime.utcnow(),
                           message_count=session.get('message_count', 0) + 1 if session else 1)

        global _LAST_DEBUG_INFO
        _LAST_DEBUG_INFO = debug_info

        return {
            "success": True,
            "response": response_text,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "audio": audio_base64,
            "debug": {
                "llm_time": debug_info.get("llm", {}).get("generation_time", 0),
                "tts_time": debug_info.get("tts", {}).get("synthesis_time", 0),
                "total_time": debug_info.get("total_time", 0),
            }
        }
    except Exception as e:
        if 'debug_info' in locals():
            _LAST_DEBUG_INFO = debug_info
        raise HTTPException(status_code=500, detail="处理语音输入时发生内部错误")


async def stream_chat_response(
    controller,
    user_input: str,
    character_id: str,
    model_name: str,
    temperature: float,
    top_p: float,
    user_id: int,
    emotion: str = "neutral",
    session_id: str = None,
) -> AsyncGenerator[str, None]:
    from database import get_db, create_session, get_session, update_session

    print(f"[API] stream_chat_response called with session_id: {session_id}")
    db = get_db()
    actual_session_id = session_id
    session = None

    if actual_session_id:
        session = get_session(db, actual_session_id)
        print(
            f"[API] Found session: {session is not None}, user_id match: {session and session['user_id'] == user_id}")
        if not session or session['user_id'] != user_id:
            actual_session_id = None
            session = None
        else:
            controller.switch_session(actual_session_id, user_id)
            print(f"[API] Switched to session: {actual_session_id}")

    if not actual_session_id:
        actual_character_id = character_id or controller.get_current_character_id()
        if actual_character_id:
            actual_session_id = create_session(
                db, user_id, actual_character_id)
            print(
                f"[API] Created new session: {actual_session_id} for character: {actual_character_id}")
        else:
            print(
                f"[API] Warning: No character_id available, session will not be created")

    try:
        async for event in controller.process_stream(
            user_input,
            temperature=temperature,
            top_p=top_p,
            character_id=character_id,
            model_name=model_name,
            user_id=user_id,
            emotion=emotion,
            session_id=actual_session_id,
        ):
            event_type = event.get("type")

            if event_type == "text":
                data = json.dumps({"content": event.get(
                    "content", "")}, ensure_ascii=False)
                yield f"event: text\ndata: {data}\n\n"

            elif event_type == "audio":
                data = json.dumps({
                    "audio": event.get("audio", ""),
                    "text": event.get("text", "")
                }, ensure_ascii=False)
                yield f"event: audio\ndata: {data}\n\n"

            elif event_type == "done":
                if actual_session_id:
                    session = get_session(db, actual_session_id)
                    update_session(db, actual_session_id,
                                   last_message_at=datetime.utcnow(),
                                   message_count=session.get('message_count', 0) + 1 if session else 1)
                data = json.dumps({
                    "conversation_id": event.get("conversation_id"),
                    "session_id": actual_session_id
                }, ensure_ascii=False)
                yield f"event: done\ndata: {data}\n\n"

            elif event_type == "error":
                data = json.dumps(
                    {"error": event.get("error", "Unknown error")}, ensure_ascii=False)
                yield f"event: error\ndata: {data}\n\n"

    except Exception as e:
        error_data = json.dumps({"error": "流式响应发生错误"}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(data: ChatRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    controller = get_controller(character_id=data.character_id)

    return StreamingResponse(
        stream_chat_response(
            controller=controller,
            user_input=data.message.strip(),
            character_id=data.character_id,
            model_name=data.model,
            temperature=data.temperature,
            top_p=data.top_p,
            user_id=user['user_id'],
            emotion=data.emotion,
            session_id=data.session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/chat/stream")
async def chat_stream_get(
    message: str,
    token: str,
    character_id: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = 1.0,
    top_p: Optional[float] = 0.9,
    emotion: Optional[str] = None,
    session_id: Optional[str] = None,
):
    user = await get_current_user_from_query(token)
    from voice_chat import get_controller

    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    controller = get_controller(character_id=character_id)

    return StreamingResponse(
        stream_chat_response(
            controller=controller,
            user_input=message.strip(),
            character_id=character_id,
            model_name=model,
            temperature=temperature,
            top_p=top_p,
            user_id=user['user_id'],
            emotion=emotion,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


class LLMChatRequest(BaseModel):
    message: str
    character_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 0.9
    use_rag: Optional[bool] = True


@app.post("/api/llm/chat")
async def llm_chat(data: LLMChatRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from database import get_db, save_llm_test_conversation

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    print(
        f"[LLM Chat] 收到请求: model={data.model}, character_id={data.character_id}, use_rag={data.use_rag}")

    try:
        controller = get_controller(character_id=data.character_id)

        response_text, debug_info = controller.llm_chat(
            data.message.strip(),
            temperature=data.temperature,
            top_p=data.top_p,
            model_name=data.model,
            use_rag=data.use_rag,
        )

        print(
            f"[LLM Chat] 成功: model={debug_info.get('model')}, response_time={debug_info.get('response_time')}")

        if response_text:
            try:
                preview = response_text[:100].encode(
                    'utf-8', errors='replace').decode('utf-8')
                print(f"[LLM Chat] 回复内容: {preview}...")
            except:
                print(f"[LLM Chat] 回复内容: (无法显示，长度={len(response_text)})")
        else:
            print(f"[LLM Chat] 回复内容: EMPTY")

        db = get_db()
        save_llm_test_conversation(
            db,
            user_id=user['user_id'],
            model=data.model or LLM_MODEL,
            user_input=data.message.strip(),
            bot_reply=response_text,
            character_id=data.character_id,
            temperature=data.temperature,
            top_p=data.top_p,
            use_rag=data.use_rag,
            response_time=debug_info.get('response_time'),
            input_tokens=debug_info.get('input_tokens'),
            output_tokens=debug_info.get('output_tokens'),
        )

        global _LAST_DEBUG_INFO
        _LAST_DEBUG_INFO = debug_info

        return {
            "success": True,
            "response": response_text,
            "debug": {
                "model": debug_info.get("model"),
                "response_time": debug_info.get("response_time", 0),
                "input_tokens": debug_info.get("input_tokens", 0),
                "output_tokens": debug_info.get("output_tokens", 0),
                "history_turns": debug_info.get("history_turns", 0),
                "use_rag": debug_info.get("use_rag"),
            }
        }
    except Exception as e:
        import traceback
        print(f"[LLM Chat] 错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="LLM对话处理失败")


@app.post("/api/llm/clear")
async def llm_clear(user: dict = Depends(get_current_user)):
    from voice_chat import get_controller

    controller = get_controller()
    controller.clear_history()

    return {"success": True, "message": "LLM历史已清除"}


class LLMChatDirectRequest(BaseModel):
    message: str
    provider_type: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    temperature: float = 1.0
    top_p: float = 0.9
    system_prompt: str = ""


@app.post("/api/llm/chat-direct")
async def llm_chat_direct(data: LLMChatDirectRequest, user: dict = Depends(get_current_user)):
    import time
    from llm_provider import get_provider, APIConfig

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    print(
        f"[LLM Chat Direct] 收到请求: provider={data.provider_type}, model={data.model_name}")

    try:
        if data.provider_type == "ollama":
            config = APIConfig(
                provider_type="ollama",
                model_name=data.model_name or LLM_MODEL
            )
        else:
            if not data.base_url or not data.api_key or not data.model_name:
                raise HTTPException(
                    status_code=400, detail="API模式需要填写完整的API配置")
            config = APIConfig(
                provider_type="openai_compatible",
                base_url=data.base_url,
                api_key=data.api_key,
                model_name=data.model_name
            )

        provider = get_provider(config)

        messages = []
        if data.system_prompt and data.system_prompt.strip():
            messages.append(
                {"role": "system", "content": data.system_prompt.strip()})
        messages.append({"role": "user", "content": data.message.strip()})

        start_time = time.time()
        result = provider.generate(
            messages,
            temperature=data.temperature,
            top_p=data.top_p,
            max_tokens=2048
        )
        response_time = time.time() - start_time

        response_text = result.get("content", "")
        usage = result.get("usage", {})

        print(f"[LLM Chat Direct] 成功: response_time={response_time:.2f}s")

        return {
            "success": True,
            "response": response_text,
            "debug": {
                "model": data.model_name,
                "provider": data.provider_type,
                "response_time": round(response_time, 2),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "history_turns": 0,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[LLM Chat Direct] 错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="LLM对话处理失败")


class APIConfigRequest(BaseModel):
    provider_type: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""


class LLMTestRequest(BaseModel):
    provider_type: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""


@app.get("/api/characters/{char_id}/api-config")
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


@app.put("/api/characters/{char_id}/api-config")
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


@app.post("/api/llm/test")
async def test_llm_connection(data: LLMTestRequest, user: dict = Depends(get_current_user)):
    from llm_provider import get_provider, APIConfig

    config = APIConfig(
        provider_type=data.provider_type,
        base_url=data.base_url,
        api_key=data.api_key,
        model_name=data.model_name,
    )
    provider = get_provider(config)
    result = provider.test_connection()
    return {"success": True, "test_result": result}


@app.post("/api/chat/rating")
async def rate_conversation(data: RatingRequest, user: dict = Depends(get_current_user)):
    from database import get_db, update_rating, set_needs_feedback, get_conversation_by_id
    from persona_manager import get_persona_manager

    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="评分必须在1-5之间")

    db = get_db()
    conv = get_conversation_by_id(db, data.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话记录不存在")

    success = update_rating(db, data.conversation_id, data.rating)
    if not success:
        raise HTTPException(status_code=500, detail="评分保存失败")

    if data.rating >= 4:
        persona_manager = get_persona_manager()
        persona_manager.save_dialogue(
            user_input=conv.get('user_input', ''),
            assistant_response=conv.get('bot_reply', ''),
            rating=data.rating,
        )
        return {
            "success": True,
            "message": "评分已保存，对话已加入知识库",
            "needs_feedback": False
        }
    else:
        set_needs_feedback(db, data.conversation_id, True)
        return {
            "success": True,
            "message": "评分已保存，请提供详细反馈以帮助我们改进",
            "needs_feedback": True
        }


@app.post("/api/chat/feedback")
async def submit_feedback_detail(data: FeedbackDetailRequest, user: dict = Depends(get_current_user)):
    from database import get_db, save_feedback_detail, get_conversation_by_id
    from feedback_types import FeedbackType
    from rag_iteration import RAGIterationManager
    from llm_provider import get_provider
    from character_config import CharacterConfigManager

    valid_types = [ft.value for ft in FeedbackType]
    if data.feedback_type not in valid_types and data.feedback_type != 'general':
        raise HTTPException(
            status_code=400, detail=f"无效的反馈类型，可选值: {', '.join(valid_types)}, general")

    db = get_db()
    conv = get_conversation_by_id(db, data.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话记录不存在")

    manager = CharacterConfigManager()
    char = manager.get_character(conv.get('character', ''))
    character_info = char.llm_config.system_prompt if char else ""

    provider = None
    if char and char.api_config and char.api_config.provider_type != "ollama":
        provider = get_provider(char.api_config)

    iteration_manager = RAGIterationManager(llm_provider=provider)

    conversation_data = {
        "user_input": conv.get("user_input", ""),
        "bot_reply": conv.get("bot_reply", ""),
        "model_name": conv.get("character", ""),
    }

    analysis_result = iteration_manager.process_feedback(
        feedback_type=data.feedback_type,
        conversation_data=conversation_data,
        character_info=character_info,
    )

    feedback_id = save_feedback_detail(
        db,
        conversation_id=data.conversation_id,
        user_id=user['user_id'],
        feedback_type=data.feedback_type,
        context_snapshot=conversation_data,
        correction_suggestion=json.dumps(analysis_result, ensure_ascii=False) if isinstance(
            analysis_result, dict) else str(analysis_result),
        model_name=conversation_data.get("model_name", ""),
    )

    if not feedback_id:
        raise HTTPException(status_code=500, detail="反馈保存失败")

    return {
        "success": True,
        "message": "反馈已保存，分析完成",
        "feedback_id": feedback_id,
        "analysis": analysis_result
    }


@app.get("/api/chat/feedback/stats")
async def get_feedback_stats(user: dict = Depends(get_current_user), model_name: Optional[str] = None):
    from database import get_db, get_think_leak_stats

    db = get_db()
    stats = get_think_leak_stats(db, model_name=model_name)

    return {"success": True, "stats": stats}


@app.get("/api/rag/iteration/{conversation_id}")
async def get_rag_iteration(conversation_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_details

    db = get_db()
    feedbacks = get_feedback_details(db, conversation_id=conversation_id, limit=1)
    
    if not feedbacks:
        return {"success": True, "has_result": False}
    
    feedback = feedbacks[0]
    return {
        "success": True,
        "has_result": True,
        "result": {
            "id": feedback["id"],
            "feedback_type": feedback["feedback_type"],
            "correction_suggestion": feedback["correction_suggestion"],
            "created_at": feedback["created_at"].isoformat() if feedback["created_at"] else None,
            "confirmed": feedback.get("confirmed", False),
        }
    }


@app.post("/api/rag/iteration")
async def trigger_rag_iteration(data: RAGIterationRequest, user: dict = Depends(get_current_user)):
    from database import get_db, get_conversation_by_id
    from rag_iteration import RAGIterationManager, get_iteration_api_config
    from llm_provider import get_provider
    from character_config import CharacterConfigManager

    db = get_db()
    conv = get_conversation_by_id(db, data.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    manager = CharacterConfigManager()
    char = manager.get_character(conv.get('character', ''))
    character_info = char.llm_config.system_prompt if char else ""

    provider = None
    iteration_api_config = get_iteration_api_config(char)
    if iteration_api_config is None:
        return {
            "success": False,
            "error": "iteration_api_not_configured",
            "message": "使用本地模型进行迭代分析效果有限，建议配置专用迭代 API（如 OpenRouter 免费模型）以获得更好的分析结果"
        }
    provider = get_provider(iteration_api_config)

    iteration_manager = RAGIterationManager(llm_provider=provider)

    conversation_data = {
        "user_input": conv.get("user_input", ""),
        "bot_reply": conv.get("bot_reply", ""),
        "model_name": conv.get("character", ""),
    }

    result = await asyncio.to_thread(
        iteration_manager.process_feedback,
        feedback_type=data.feedback_type,
        conversation_data=conversation_data,
        character_info=character_info,
    )

    from database import save_feedback_detail
    feedback_id = save_feedback_detail(
        db,
        conversation_id=data.conversation_id,
        user_id=user['user_id'],
        feedback_type=data.feedback_type,
        context_snapshot=conversation_data,
        correction_suggestion=json.dumps(result, ensure_ascii=False) if isinstance(
            result, dict) else str(result),
        model_name=conversation_data.get("model_name", ""),
    )

    return {"success": True, "analysis": result, "feedback_id": feedback_id}


class RAGEditConfirmRequest(BaseModel):
    feedback_detail_id: int
    edited_suggestion: Optional[str] = None


@app.post("/api/rag/iteration/edit-confirm")
async def edit_and_confirm_rag_iteration(data: RAGEditConfirmRequest, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_detail_by_id, confirm_feedback_detail, update_feedback_rag_status

    db = get_db()
    feedback_detail = get_feedback_detail_by_id(db, data.feedback_detail_id)

    if not feedback_detail:
        raise HTTPException(status_code=404, detail="反馈记录不存在")

    if feedback_detail['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权确认此反馈")

    if feedback_detail.get('confirmed'):
        return {"success": True, "message": "该反馈已确认", "already_confirmed": True}

    if data.edited_suggestion:
        try:
            with db.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE feedback_details SET correction_suggestion = %s WHERE id = %s",
                    (data.edited_suggestion, data.feedback_detail_id)
                )
        except Exception as e:
            print(f"[RAG Edit] 更新建议内容失败: {e}")
            raise HTTPException(status_code=500, detail="更新建议内容失败")

    success = confirm_feedback_detail(db, data.feedback_detail_id, user['user_id'])
    if not success:
        raise HTTPException(status_code=500, detail="确认失败")

    return {
        "success": True,
        "message": "反馈已确认，可以更新到RAG知识库",
        "feedback_detail_id": data.feedback_detail_id
    }


@app.post("/api/rag/iteration/confirm")
async def confirm_rag_iteration(data: RAGConfirmRequest, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_detail_by_id, confirm_feedback_detail, update_feedback_rag_status

    db = get_db()
    feedback_detail = get_feedback_detail_by_id(db, data.feedback_detail_id)

    if not feedback_detail:
        raise HTTPException(status_code=404, detail="反馈记录不存在")

    if feedback_detail['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权确认此反馈")

    if feedback_detail.get('confirmed'):
        return {"success": True, "message": "该反馈已确认", "already_confirmed": True}

    success = confirm_feedback_detail(
        db, data.feedback_detail_id, user['user_id'])
    if not success:
        raise HTTPException(status_code=500, detail="确认失败")

    correction_suggestion = feedback_detail.get('correction_suggestion')
    rag_updated = False

    if correction_suggestion:
        try:
            from persona_manager import get_persona_manager
            persona_manager = get_persona_manager()

            suggestion_data = json.loads(correction_suggestion) if isinstance(
                correction_suggestion, str) else correction_suggestion

            if isinstance(suggestion_data, dict):
                knowledge_content = None

                if 'errors' in suggestion_data and suggestion_data['errors']:
                    first_error = suggestion_data['errors'][0]
                    knowledge_content = f"修正: {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
                elif 'deviations' in suggestion_data and suggestion_data['deviations']:
                    first_deviation = suggestion_data['deviations'][0]
                    knowledge_content = f"角色修正: {first_deviation.get('aspect', '')} - {first_deviation.get('suggestion', '')}"
                elif 'forgotten_points' in suggestion_data and suggestion_data['forgotten_points']:
                    first_point = suggestion_data['forgotten_points'][0]
                    knowledge_content = f"记忆点: {first_point.get('point', '')}"
                elif 'overall_suggestion' in suggestion_data:
                    knowledge_content = suggestion_data['overall_suggestion']
                elif 'analyses' in suggestion_data:
                    for analysis_type, analysis in suggestion_data['analyses'].items():
                        if isinstance(analysis, dict) and 'overall_suggestion' in analysis:
                            knowledge_content = analysis['overall_suggestion']
                            break

                if knowledge_content:
                    context_snapshot = feedback_detail.get('context_snapshot')
                    if isinstance(context_snapshot, str):
                        context_snapshot = json.loads(context_snapshot)

                    persona_manager.add_knowledge_entry(
                        content=knowledge_content,
                        metadata={
                            "source": "feedback_correction",
                            "feedback_id": data.feedback_detail_id,
                            "feedback_type": feedback_detail.get('feedback_type'),
                            "user_input": context_snapshot.get('user_input', '') if context_snapshot else '',
                        }
                    )
                    rag_updated = True
                    update_feedback_rag_status(
                        db, data.feedback_detail_id, True)
        except Exception as e:
            print(f"[RAG Confirm] 添加知识条目失败: {e}")

    return {
        "success": True,
        "message": "反馈已确认" + ("，知识条目已添加到RAG" if rag_updated else ""),
        "rag_updated": rag_updated
    }


@app.get("/api/rag/feedback/{conversation_id}")
async def get_conversation_feedback(conversation_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, get_feedback_details

    db = get_db()
    feedbacks = get_feedback_details(
        db, conversation_id=conversation_id, user_id=user['user_id'])

    return {
        "success": True,
        "feedbacks": feedbacks
    }


@app.post("/api/rag/update")
async def update_rag_knowledge(user: dict = Depends(get_current_user)):
    from database import get_db, get_unprocessed_rag_feedbacks, update_feedback_rag_status
    from persona_manager import get_persona_manager
    import json

    db = get_db()
    feedbacks = get_unprocessed_rag_feedbacks(db, limit=100)

    if not feedbacks:
        return {
            "success": True,
            "message": "没有待更新的知识条目",
            "updated_count": 0
        }

    persona_manager = get_persona_manager()
    updated_count = 0
    errors = []

    for feedback in feedbacks:
        try:
            correction_suggestion = feedback.get('correction_suggestion')
            if not correction_suggestion:
                continue

            suggestion_data = None
            if isinstance(correction_suggestion, str):
                try:
                    suggestion_data = json.loads(correction_suggestion)
                except json.JSONDecodeError:
                    suggestion_data = {"raw_suggestion": correction_suggestion}
            else:
                suggestion_data = correction_suggestion

            knowledge_content = None

            if isinstance(suggestion_data, dict):
                if 'errors' in suggestion_data and suggestion_data['errors']:
                    first_error = suggestion_data['errors'][0]
                    knowledge_content = f"修正: {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
                elif 'deviations' in suggestion_data and suggestion_data['deviations']:
                    first_deviation = suggestion_data['deviations'][0]
                    knowledge_content = f"角色修正: {first_deviation.get('aspect', '')} - {first_deviation.get('suggestion', '')}"
                elif 'forgotten_points' in suggestion_data and suggestion_data['forgotten_points']:
                    first_point = suggestion_data['forgotten_points'][0]
                    knowledge_content = f"记忆点: {first_point.get('point', '')}"
                elif 'overall_suggestion' in suggestion_data:
                    knowledge_content = suggestion_data['overall_suggestion']
                elif 'analyses' in suggestion_data:
                    for analysis_type, analysis in suggestion_data['analyses'].items():
                        if isinstance(analysis, dict) and 'overall_suggestion' in analysis:
                            knowledge_content = analysis['overall_suggestion']
                            break
                        elif isinstance(analysis, dict) and 'errors' in analysis and analysis['errors']:
                            first_error = analysis['errors'][0]
                            knowledge_content = f"修正({analysis_type}): {first_error.get('content', '')} -> {first_error.get('suggestion', '')}"
                            break
                elif 'raw_suggestion' in suggestion_data:
                    knowledge_content = suggestion_data['raw_suggestion']

            if knowledge_content:
                context_snapshot = feedback.get('context_snapshot')
                if isinstance(context_snapshot, str):
                    try:
                        context_snapshot = json.loads(context_snapshot)
                    except:
                        context_snapshot = {}

                user_input = context_snapshot.get(
                    'user_input', '') if context_snapshot else feedback.get('conv_user_input', '')
                bot_reply = context_snapshot.get(
                    'bot_reply', '') if context_snapshot else feedback.get('conv_bot_reply', '')

                combined_knowledge = knowledge_content
                if user_input and bot_reply:
                    combined_knowledge = f"用户问: {user_input}\n助手答: {bot_reply}\n修正建议: {knowledge_content}"

                persona_manager.add_knowledge_entry(
                    content=combined_knowledge,
                    metadata={
                        "source": "feedback_correction",
                        "feedback_id": feedback['id'],
                        "feedback_type": feedback.get('feedback_type'),
                        "user_input": user_input,
                    }
                )

                update_feedback_rag_status(db, feedback['id'], True)
                updated_count += 1

        except Exception as e:
            errors.append(f"反馈ID {feedback['id']}: {str(e)}")
            continue

    return {
        "success": True,
        "message": f"成功更新 {updated_count} 条知识到RAG知识库",
        "updated_count": updated_count,
        "total_found": len(feedbacks),
        "errors": errors if errors else None
    }


@app.get("/api/rag/status")
async def get_rag_status(user: dict = Depends(get_current_user)):
    from build_rag import get_rag_collection_info
    from character_config import CharacterConfigManager

    manager = CharacterConfigManager()
    characters = manager.get_all_characters()
    collection_info = get_rag_collection_info()

    status_list = []
    for char in characters:
        coll_name = char.rag_config.collection_name
        matching = [c for c in collection_info if c["collection_name"] == coll_name]
        doc_count = matching[0]["document_count"] if matching else 0

        status_list.append({
            "character_id": char.id,
            "character_name": char.name,
            "collection_name": coll_name,
            "rag_enabled": char.rag_config.enabled,
            "document_count": doc_count,
            "has_collection": len(matching) > 0,
        })

    return {"success": True, "status": status_list}


@app.post("/api/rag/build")
async def build_rag_from_txt(request: dict, user: dict = Depends(get_current_user)):
    from build_rag import build_character_rag
    from character_config import CharacterConfigManager

    character_id = request.get("character_id")
    text_content = request.get("text_content", "")

    if not character_id or not text_content.strip():
        return {"success": False, "message": "请提供角色ID和文本内容"}

    manager = CharacterConfigManager()
    character = manager.get_character(character_id)
    if not character:
        return {"success": False, "message": "角色不存在"}

    collection_name = character.rag_config.collection_name
    if not collection_name:
        collection_name = f"{character_id}_knowledge"
        character.rag_config.collection_name = collection_name
        manager.update_character(character)

    try:
        collection, _ = build_character_rag(
            character_id=character_id,
            character_name=character.name,
            collection_name=collection_name,
            text_content=text_content,
        )
        if collection:
            return {"success": True, "message": f"RAG 知识库构建成功，共 {collection.count()} 条文档"}
        else:
            return {"success": False, "message": "RAG 知识库构建失败"}
    except Exception as e:
        return {"success": False, "message": f"构建失败: {str(e)}"}


@app.delete("/api/rag/{collection_name}")
async def delete_rag(collection_name: str, user: dict = Depends(get_current_user)):
    from build_rag import delete_rag_collection

    success = delete_rag_collection(collection_name)
    if success:
        return {"success": True, "message": "RAG 集合已删除"}
    else:
        return {"success": False, "message": "删除失败"}


@app.get("/api/chat/history")
async def get_chat_history(user: dict = Depends(get_current_user), limit: int = 20):
    from database import get_db, get_conversations

    db = get_db()
    conversations = get_conversations(db, user['user_id'], limit)

    result = []
    for conv in conversations:
        result.append({
            "id": conv['id'],
            "character": conv['character'],
            "user_input": conv['user_input'],
            "bot_reply": conv['bot_reply'],
            "rating": conv['rating'],
            "timestamp": str(conv['timestamp']) if conv.get('timestamp') else None,
            "session_id": conv.get('session_id'),
        })

    return {"success": True, "conversations": result}


@app.post("/api/sessions")
async def create_session(data: SessionCreate, user: dict = Depends(get_current_user)):
    from database import get_db, create_session as db_create_session

    db = get_db()
    session_id = db_create_session(
        db, user['user_id'], data.character_id, data.title)

    if not session_id:
        raise HTTPException(status_code=500, detail="创建会话失败")

    return {
        "success": True,
        "session_id": session_id,
        "session": {
            "id": session_id,
            "user_id": user['user_id'],
            "character_id": data.character_id,
            "title": data.title,
            "message_count": 0,
        }
    }


@app.get("/api/sessions")
async def get_sessions(user: dict = Depends(get_current_user), limit: int = 50):
    from database import get_db, get_user_sessions

    db = get_db()
    sessions = get_user_sessions(db, user['user_id'], limit)

    result = []
    for session in sessions:
        result.append({
            "id": session['id'],
            "character_id": session['character_id'],
            "title": session['title'],
            "last_message_at": str(session['last_message_at']) if session.get('last_message_at') else None,
            "created_at": str(session['created_at']) if session.get('created_at') else None,
            "message_count": session.get('message_count', 0),
        })

    return {"success": True, "sessions": result}


@app.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, get_session, get_session_conversations

    db = get_db()
    session = get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    conversations = get_session_conversations(db, session_id)

    messages = []
    for conv in conversations:
        messages.append({
            "id": conv['id'],
            "user_input": conv['user_input'],
            "bot_reply": conv['bot_reply'],
            "rating": conv['rating'],
            "timestamp": str(conv['timestamp']) if conv.get('timestamp') else None,
        })

    return {
        "success": True,
        "session": {
            "id": session['id'],
            "character_id": session['character_id'],
            "title": session['title'],
            "last_message_at": str(session['last_message_at']) if session.get('last_message_at') else None,
            "created_at": str(session['created_at']) if session.get('created_at') else None,
            "message_count": session.get('message_count', 0),
        },
        "messages": messages
    }


@app.post("/api/sessions/{session_id}/restore")
async def restore_session(session_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, get_session
    from voice_chat import get_controller

    db = get_db()
    session = get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    controller = get_controller()
    success = controller.switch_session(session_id, user['user_id'])

    if not success:
        raise HTTPException(status_code=500, detail="会话恢复失败")

    return {
        "success": True,
        "message": "会话已恢复",
        "session": {
            "id": session['id'],
            "character_id": session['character_id'],
            "title": session['title'],
            "message_count": session.get('message_count', 0),
        },
        "history_turns": controller.llm.get_history_length()
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session_by_id(session_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, get_session, delete_session as db_delete_session

    db = get_db()
    session = get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权删除该会话")

    success = db_delete_session(db, session_id)

    if not success:
        raise HTTPException(status_code=500, detail="删除会话失败")

    return {"success": True, "message": "会话已删除"}


@app.put("/api/chat/sessions/{session_id}/title")
async def update_session_title(session_id: str, title_data: dict, user: dict = Depends(get_current_user)):
    from database import get_db, update_conversation_title
    db = get_db()
    success = update_conversation_title(db, session_id, user['user_id'], title_data.get('title', ''))
    if success:
        return {"success": True, "message": "标题更新成功"}
    raise HTTPException(status_code=404, detail="会话不存在")


@app.get("/api/chat/search")
async def search_user_conversations(keyword: Optional[str] = None, character: Optional[str] = None,
                                    limit: int = 50, offset: int = 0,
                                    user: dict = Depends(get_current_user)):
    from database import search_conversations, count_search_results, get_db
    db = get_db()
    results = search_conversations(db, keyword=keyword, user_id=user['user_id'],
                                   character=character, limit=limit, offset=offset)
    total = count_search_results(
        db, keyword=keyword, user_id=user['user_id'], character=character)
    return {"success": True, "results": results, "total": total, "limit": limit, "offset": offset}


@app.post("/api/chat/clear")
async def clear_chat_history(user: dict = Depends(get_current_user)):
    from voice_chat import get_controller

    controller = get_controller()
    controller.clear_history()

    return {"success": True, "message": "对话历史已清除"}


@app.get("/api/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    from database import get_db, get_user_profile
    from profile_summary import get_profile_summary_manager

    db = get_db()
    profile = get_user_profile(db, user['user_id'])

    manager = get_profile_summary_manager()
    should_regenerate = manager.should_regenerate(user['user_id'])

    return {
        "success": True,
        "profile": {
            "summary": profile.get('profile_summary') if profile else None,
            "total_tokens": profile.get('total_tokens', 0) if profile else 0,
            "last_updated": str(profile['last_updated']) if profile and profile.get('last_updated') else None,
        },
        "should_regenerate": should_regenerate,
    }


@app.post("/api/profile/regenerate")
async def regenerate_profile(user: dict = Depends(get_current_user)):
    from profile_summary import get_profile_summary_manager

    manager = get_profile_summary_manager()
    summary = manager.update_profile_summary(user['user_id'])

    if not summary:
        raise HTTPException(status_code=500, detail="画像生成失败，请确保有足够的对话历史")

    return {
        "success": True,
        "message": "画像已重新生成",
        "summary": summary,
    }


@app.get("/api/tts")
async def text_to_speech(text: str, speed: float = 1.0, emotion: str = "neutral", character_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    import base64

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    try:
        controller = get_controller()
        audio_bytes = controller.synthesize_audio(
            text.strip(), speed=speed, emotion=emotion, character_id=character_id)

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="语音合成失败")

        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {"success": True, "audio": audio_base64, "emotion": emotion}
    except Exception as e:
        raise HTTPException(status_code=500, detail="语音合成失败")


class TTSEmotionRequest(BaseModel):
    text: str
    emotion: str = "neutral"
    character_id: Optional[str] = None
    speed: float = 1.0


@app.post("/api/tts/emotion")
async def text_to_speech_emotion(data: TTSEmotionRequest, user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    import base64

    if not data.text or not data.text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    try:
        controller = get_controller()
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


@app.get("/api/tts/config")
async def get_tts_config(user: dict = Depends(get_current_user)):
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


@app.get("/api/tts/emotion-config")
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


@app.get("/api/characters/my")
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


@app.post("/api/characters/my")
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


@app.put("/api/characters/my/{user_character_id}")
async def update_my_character(user_character_id: int, data: UserCharacterUpdate, user: dict = Depends(get_current_user)):
    from database import get_db, update_user_character

    db = get_db()
    success = update_user_character(
        db, user_character_id, data.character_data, user_id=user['user_id'])

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在或无权限")

    return {"success": True, "message": "角色已更新"}


@app.delete("/api/characters/my/{user_character_id}")
async def delete_my_character(user_character_id: int, user: dict = Depends(get_current_user)):
    from database import get_db, delete_user_character

    db = get_db()
    success = delete_user_character(
        db, user_character_id, user_id=user['user_id'])

    if not success:
        raise HTTPException(status_code=404, detail="角色不存在或无权限")

    return {"success": True, "message": "角色已删除"}


@app.get("/api/pet/emotion")
async def pet_emotion_stream(user: dict = Depends(get_current_user)):
    import asyncio

    async def emotion_generator():
        last_emotion = "neutral"
        while True:
            try:
                from voice_chat import get_controller
                controller = get_controller()
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


@app.get("/api/security/status")
async def get_security_status(user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "enabled": _security_filter.enabled,
        "intercept_count": len(_security_filter.intercept_log),
    }


@app.get("/api/security/log")
async def get_security_log(limit: int = 100, user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "log": _security_filter.get_intercept_log(limit=limit),
    }


@app.put("/api/security/toggle")
async def toggle_security_filter(enabled: bool, user: dict = Depends(get_current_user)):
    _security_filter.enabled = enabled
    return {
        "success": True,
        "enabled": _security_filter.enabled,
        "message": f"安全过滤器已{'启用' if enabled else '禁用'}",
    }


@app.get("/api/system/status")
async def get_system_status(user: dict = Depends(get_current_user)):
    from voice_chat import get_controller
    from tts_service import check_gpu_memory

    controller = get_controller()
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


@app.get("/api/system/backgrounds")
async def get_background_images():
    import glob
    images_dir = PATH_CONFIG.get("images_dir", "")
    print(f"[Background] 检查目录: {images_dir}")

    if not os.path.exists(images_dir):
        print(f"[Background] 目录不存在: {images_dir}")
        return {"success": False, "images": []}

    patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
    images = []
    for pattern in patterns:
        found = glob.glob(os.path.join(images_dir, pattern))
        print(f"[Background] 模式 {pattern} 找到 {len(found)} 个文件")
        images.extend(found)

    print(f"[Background] 总共找到 {len(images)} 个图片文件")

    image_names = [os.path.basename(f) for f in images]
    print(f"[Background] 使用全部 {len(image_names)} 个图片")

    image_urls = [f"/images/{quote(name)}" for name in image_names[:20]]
    print(f"[Background] 返回 {len(image_urls)} 个URL")

    return {"success": True, "images": image_urls}


@app.get("/api/debug-info")
async def get_debug_info(user: dict = Depends(get_current_user)):
    global _LAST_DEBUG_INFO

    if _LAST_DEBUG_INFO is None:
        return {
            "success": True,
            "debug_info": None,
            "message": "暂无调试信息，请先进行一次对话"
        }

    return {
        "success": True,
        "debug_info": _LAST_DEBUG_INFO
    }


@app.get("/api/settings")
async def get_admin_settings(user: dict = Depends(get_current_user)):
    from database import get_db, get_settings
    db = get_db()
    saved = get_settings(db)
    return {
        "success": True,
        "settings": {
            "securityFilterEnabled": saved.get("securityFilterEnabled", _security_filter.enabled),
            "proxyEnabled": saved.get("proxyEnabled", False),
            "proxyUrl": saved.get("proxyUrl", ""),
            "verboseLogging": saved.get("verboseLogging", False),
        }
    }


@app.put("/api/settings")
async def update_admin_settings(settings: dict, user: dict = Depends(get_current_user)):
    from database import get_db, save_settings
    if "securityFilterEnabled" in settings:
        _security_filter.enabled = settings["securityFilterEnabled"]

    db = get_db()
    save_settings(db, settings)

    return {
        "success": True,
        "message": "设置已保存",
        "settings": {
            "securityFilterEnabled": _security_filter.enabled,
            "proxyEnabled": settings.get("proxyEnabled", False),
            "proxyUrl": settings.get("proxyUrl", ""),
            "verboseLogging": settings.get("verboseLogging", False),
        }
    }


@app.post("/api/config/reload")
async def reload_config(user: dict = Depends(get_current_user)):
    manager = get_config_manager()
    reloaded = manager.check_and_reload()

    return {
        "success": True,
        "reloaded": reloaded,
        "message": "配置已重新加载" if reloaded else "配置无变化",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/config/status")
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


@app.get("/api/conversations/{conv_id}/export")
async def export_conversation(
    conv_id: int,
    format: str = "markdown",
    user: dict = Depends(get_current_user)
):
    from database import get_db, get_conversation_by_user

    db = get_db()
    conversation = get_conversation_by_user(db, conv_id, user['user_id'])

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


@app.get("/api/user/preference/stats")
async def get_preference_stats(user: dict = Depends(get_current_user), days: int = 30):
    from database import get_db, get_preference_stats, get_total_conversation_count

    db = get_db()
    stats = get_preference_stats(db, user['user_id'], days)

    total_conversations = get_total_conversation_count(db, user['user_id'])
    total_rated_conversations = sum(stats['rating_distribution'].values())
    avg_rating = 0
    if total_rated_conversations > 0:
        weighted_sum = sum(
            r * c for r, c in stats['rating_distribution'].items())
        avg_rating = round(weighted_sum / total_rated_conversations, 2)

    return {
        "success": True,
        "stats": {
            "top_positive_keywords": stats['top_positive_keywords'],
            "top_negative_keywords": stats['top_negative_keywords'],
            "interest_keywords": stats['interest_keywords'],
            "rating_distribution": stats['rating_distribution'],
            "conversation_trend": [
                {"date": str(item['date']), "count": item['count']}
                for item in stats['conversation_trend']
            ],
            "summary": {
                "total_conversations": total_conversations,
                "total_rated_conversations": total_rated_conversations,
                "avg_rating": avg_rating,
            }
        }
    }


@app.get("/api/memory/anchors/{character_id}")
async def get_anchors(character_id: str, user: dict = Depends(get_current_user)):
    from database import get_memory_anchors, get_db
    db = get_db()
    anchors = get_memory_anchors(
        db, user_id=user['user_id'], character_id=character_id)
    return {"anchors": anchors}


@app.post("/api/memory/anchors")
async def create_anchor(data: MemoryAnchorCreate, user: dict = Depends(get_current_user)):
    from database import save_memory_anchor, get_db
    db = get_db()
    anchor_id = save_memory_anchor(db, user_id=user['user_id'], character_id=data.character_id,
                                   content=data.content, anchor_type=data.anchor_type,
                                   importance=data.importance)
    if anchor_id:
        return {"success": True, "anchor_id": anchor_id}
    raise HTTPException(status_code=500, detail="Failed to create anchor")


@app.put("/api/memory/anchors/{anchor_id}")
async def update_anchor(anchor_id: int, data: MemoryAnchorUpdate, user: dict = Depends(get_current_user)):
    from database import update_memory_anchor, get_db
    db = get_db()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if update_memory_anchor(db, anchor_id, user_id=user['user_id'], **updates):
        return {"success": True}
    raise HTTPException(status_code=404, detail="锚点不存在或无权限")


@app.delete("/api/memory/anchors/{anchor_id}")
async def delete_anchor(anchor_id: int, user: dict = Depends(get_current_user)):
    from database import delete_memory_anchor, get_db
    db = get_db()
    if delete_memory_anchor(db, anchor_id, user_id=user['user_id']):
        return {"success": True}
    raise HTTPException(status_code=404, detail="锚点不存在或无权限")


def run_api():
    print("\n" + "=" * 50)
    print("  三月七语音对话系统启动中...")
    print("=" * 50 + "\n")

    print("[OK] FastAPI 服务已启动！")
    print("   API 文档: http://127.0.0.1:8000/docs")
    print("   前端请访问: http://localhost:5173")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run_api()
