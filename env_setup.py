"""
环境变量集中设置模块
统一管理 os.environ 的设置，避免在多个文件中重复设置
"""

import os


_initialized = False


def setup_environment():
    global _initialized
    if _initialized:
        return

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

    _initialized = True


setup_environment()
