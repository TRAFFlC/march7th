from personal_config import PATH_CONFIG, LLM_MODEL, LLM_MAX_TOKENS, TTS_CONFIG, RAG_CONFIG
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


_gpt_sovits_dir = PATH_CONFIG.get("gpt_sovits_dir", "")
if _gpt_sovits_dir:
    _gpt_path = Path(_gpt_sovits_dir)
    if not _gpt_path.is_absolute():
        GPT_SOVITS_DIR = Path(BASE_DIR / _gpt_path)
    else:
        GPT_SOVITS_DIR = _gpt_path
else:
    GPT_SOVITS_DIR = Path(BASE_DIR.parent / "GPT-SoVITS")

_tts_gpt_weight = PATH_CONFIG.get("tts_gpt_weight", "")
TTS_GPT_WEIGHT = _tts_gpt_weight if _tts_gpt_weight else str(BASE_DIR / "resources" / "tts" / "models" / "march7th-e15.ckpt")

_tts_sovits_weight = PATH_CONFIG.get("tts_sovits_weight", "")
TTS_SOVITS_WEIGHT = _tts_sovits_weight if _tts_sovits_weight else str(BASE_DIR / "resources" / "tts" / "models" / "march7th_e8_s5040.pth")

TTS_PORT = TTS_CONFIG.get("default_port", 9880)
TTS_VERSION = TTS_CONFIG.get("default_version", "v2ProPlus")

_ref_audio_path = PATH_CONFIG.get("ref_audio_path", "")
REF_AUDIO_PATH = _ref_audio_path if _ref_audio_path else str(BASE_DIR / "resources" / "tts" / "ref_audio" / "march7th_ref.wav")

REF_AUDIO_TEXT = TTS_CONFIG.get("ref_audio_text", "")

HISTORY_FILE = str(BASE_DIR / "user_persona.txt")
HISTORY_LIMIT = 50

GPU_MEMORY_THRESHOLD = 1000
MEMORY_CHECK_INTERVAL = 0.5
MAX_WAIT_TIME = 30

_embedding_model_name = RAG_CONFIG.get(
    "embedding_model", "BAAI/bge-small-zh-v1.5")
_LOCAL_MODEL_PATH = BASE_DIR / "models" / _embedding_model_name.split("/")[-1]
if _LOCAL_MODEL_PATH.exists():
    EMBEDDING_MODEL = str(_LOCAL_MODEL_PATH)
else:
    _HF_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "hub"
    _model_cache_name = _embedding_model_name.replace("/", "--")
    _BGE_LOCAL_PATH = _HF_CACHE_DIR / f"models--{_model_cache_name}" / "snapshots"
    if _BGE_LOCAL_PATH.exists():
        _snapshot_dirs = list(_BGE_LOCAL_PATH.iterdir())
        if _snapshot_dirs:
            EMBEDDING_MODEL = str(_snapshot_dirs[0])
        else:
            EMBEDDING_MODEL = _embedding_model_name
    else:
        EMBEDDING_MODEL = _embedding_model_name

RERANK_MODEL = RAG_CONFIG.get("rerank_model", "BAAI/bge-reranker-base")

PERSONA_FILE = str(BASE_DIR / "user_persona.jsonl")
PERSONA_DB_DIR = str(BASE_DIR / "persona_db")
PERSONA_MIN_RATING = 4
PERSONA_TOP_K = 2

REPETITION_DECAY = 0.7
REPETITION_RESET_HOURS = 24
REPETITION_MAX_PENALTY = 0.3

PREFERENCE_DECAY_RATE = 0.1

PROFILE_SUMMARY_TOKEN_THRESHOLD = 10000
PROFILE_SUMMARY_MAX_TOKENS = 500

RERANK_TOP_K = 3

CONFIG_AUTO_RELOAD = True
CONFIG_CHECK_INTERVAL = 30

EMOTION_CLASSIFICATION_MODE = "keyword_hybrid"

CORS_ALLOWED_ORIGINS = ["*"]
