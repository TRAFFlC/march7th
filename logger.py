import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"


def _ensure_log_dir():
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)


class Logger:
    _instance: Optional["Logger"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if Logger._initialized:
            return

        _ensure_log_dir()

        self._logger = logging.getLogger("march7th")
        self._logger.setLevel(logging.DEBUG)

        if self._logger.handlers:
            self._logger.handlers.clear()

        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_handler = logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
            mode="a"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        Logger._initialized = True

    def info(self, message: str):
        self._logger.info(message)

    def warning(self, message: str):
        self._logger.warning(message)

    def error(self, message: str):
        self._logger.error(message)

    def debug(self, message: str):
        self._logger.debug(message)

    def get_logger(self) -> logging.Logger:
        return self._logger


_logger_instance: Optional[Logger] = None


def get_logger() -> Logger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance


def log_login(username: str):
    logger = get_logger()
    logger.info(f"用户登录: {username}")


def log_logout(username: str):
    logger = get_logger()
    logger.info(f"用户登出: {username}")


def log_character_switch(username: str, character: str):
    logger = get_logger()
    logger.info(f"用户 '{username}' 切换角色至: {character}")


def log_rating(username: str, conversation_id: str, rating: int):
    logger = get_logger()
    logger.info(f"用户 '{username}' 对对话 '{conversation_id}' 评分: {rating}星")


def log_model_load(model_name: str):
    logger = get_logger()
    logger.info(f"模型加载: {model_name}")


def log_error(module: str, error: Exception | str):
    logger = get_logger()
    error_msg = str(error) if isinstance(error, Exception) else error
    logger.error(f"[{module}] {error_msg}")


def log_request(module: str, request_info: str):
    logger = get_logger()
    logger.debug(f"[{module}] 请求: {request_info}")


def log_response(module: str, response_info: str):
    logger = get_logger()
    logger.debug(f"[{module}] 响应: {response_info}")


def log_performance(module: str, operation: str, duration_ms: float):
    logger = get_logger()
    logger.debug(f"[{module}] {operation} 耗时: {duration_ms:.2f}ms")


__all__ = [
    "Logger",
    "get_logger",
    "log_login",
    "log_logout",
    "log_character_switch",
    "log_rating",
    "log_model_load",
    "log_error",
    "log_request",
    "log_response",
    "log_performance",
    "LOG_DIR",
    "LOG_FILE",
]
