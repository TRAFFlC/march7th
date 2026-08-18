"""
API 请求/响应 Pydantic 模型
"""
from typing import Optional

from pydantic import BaseModel


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
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


class RAGEditConfirmRequest(BaseModel):
    feedback_detail_id: int
    edited_suggestion: Optional[str] = None


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
    iteration_apis: Optional[list] = None
    emotion_api_config: Optional[dict] = None
    greeting_templates: Optional[dict] = None
    tts_config: Optional[dict] = None
    emotions: Optional[dict] = None


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


class LLMChatRequest(BaseModel):
    message: str
    character_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 0.9
    use_rag: Optional[bool] = True


class LLMChatDirectRequest(BaseModel):
    message: str
    provider_type: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    temperature: float = 1.0
    top_p: float = 0.9
    system_prompt: str = ""


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


class TTSEmotionRequest(BaseModel):
    text: str
    emotion: str = "neutral"
    character_id: Optional[str] = None
    speed: float = 1.0
