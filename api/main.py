"""
FastAPI 后端 API 入口：应用组装、中间件与启动
"""
from contextlib import asynccontextmanager
import logging
import os
import subprocess
import sys
import time

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from config import CONFIG_AUTO_RELOAD, CONFIG_CHECK_INTERVAL
from personal_config import CORS_ALLOWED_ORIGINS, PATH_CONFIG
from .deps import logger
from .routers import (
    admin,
    auth,
    characters,
    chat,
    community,
    llm,
    memory,
    rag,
    sessions,
    system,
    tts,
    user,
)

OLLAMA_PROCESS = None


def is_ollama_running() -> bool:
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def start_ollama_serve():
    global OLLAMA_PROCESS

    if is_ollama_running():
        logger.info("Ollama 已在运行中")
        return True

    logger.info("正在启动 Ollama 服务...")

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
            logger.error("未找到 ollama，请确保已安装 Ollama")
            return False

        logger.info("找到 Ollama: %s", ollama_path)

        if sys.platform == "win32":
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
                logger.info("Ollama 服务已启动")
                return True
            logger.info("等待 Ollama 启动... (%s/30)", i + 1)

        logger.warning("Ollama 启动超时，请手动启动")
        return False

    except FileNotFoundError:
        logger.error("未找到 ollama 命令，请确保已安装 Ollama")
        return False
    except Exception as e:
        logger.exception("启动 Ollama 失败: %s", e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    from character_config import CharacterConfigManager
    from .deps import set_config_manager

    start_ollama_serve()

    _config_manager = CharacterConfigManager(auto_reload=CONFIG_AUTO_RELOAD)
    set_config_manager(_config_manager)

    if CONFIG_AUTO_RELOAD:
        _config_manager.start_file_watcher(interval=CONFIG_CHECK_INTERVAL)
        logger.info("配置自动重载已启用，检查间隔: %s秒", CONFIG_CHECK_INTERVAL)

    yield

    if _config_manager:
        _config_manager.stop_file_watcher()
        logger.info("配置文件监控已停止")


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGES_DIR = PATH_CONFIG.get("images_dir", "")
if IMAGES_DIR and os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
    logger.info("静态图片目录已挂载: %s", IMAGES_DIR)


@app.get("/")
async def root():
    return {"message": "三月七语音对话系统 API", "version": "2.0.0"}


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(characters.router)
app.include_router(community.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(llm.router)
app.include_router(rag.router)
app.include_router(memory.router)
app.include_router(tts.router)
app.include_router(admin.router)
app.include_router(system.router)


def run_api():
    logger.info("三月七语音对话系统启动中...")
    logger.info("FastAPI 服务已启动！API 文档: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=False)
