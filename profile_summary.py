"""
用户画像自动摘要模块
User Profile Auto-Summary Module
"""

import ollama
from typing import Optional, Dict, Any, List
from datetime import datetime

import config
from database import (
    get_db,
    get_or_create_user_profile,
    get_user_profile,
    update_user_profile,
    get_conversation_tokens,
    get_recent_conversations_for_summary,
    get_preferences,
)


def _get_profile_summary_prompt(**kwargs) -> str:
    from prompt_manager import get_prompt_manager
    return get_prompt_manager().get_prompt("profile_summary", "profile_summary", **kwargs)


class ProfileSummaryManager:
    def __init__(
        self,
        token_threshold: int = None,
        max_tokens: int = None,
        model_name: str = None,
    ):
        self.token_threshold = token_threshold or getattr(config, 'PROFILE_SUMMARY_TOKEN_THRESHOLD', 10000)
        self.max_tokens = max_tokens or getattr(config, 'PROFILE_SUMMARY_MAX_TOKENS', 500)
        self.model_name = model_name or getattr(config, 'LLM_MODEL', 'deepseek-r1:8b')

    def calculate_conversation_tokens(self, user_id: int) -> int:
        db = get_db()
        return get_conversation_tokens(db, user_id)

    def generate_profile_summary(self, user_id: int) -> Optional[str]:
        db = get_db()
        
        conversations = get_recent_conversations_for_summary(db, user_id, limit=50)
        if not conversations:
            return None
        
        conv_texts = []
        for conv in conversations[-20:]:
            conv_texts.append(f"用户: {conv['user_input']}")
            conv_texts.append(f"助手: {conv['bot_reply']}")
        
        conversations_text = "\n".join(conv_texts)
        
        preferences = get_preferences(db, user_id)
        pref_texts = []
        for pref in preferences[:10]:
            sentiment = "喜欢" if pref['sentiment'] == 'positive' else "不喜欢"
            pref_texts.append(f"- {sentiment}: {pref['keyword']} (提及{pref['count']}次)")
        preferences_text = "\n".join(pref_texts) if pref_texts else "暂无偏好数据"
        
        prompt = _get_profile_summary_prompt(
            conversations=conversations_text,
            preferences=preferences_text
        )
        
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.3,
                    "num_predict": self.max_tokens,
                }
            )
            
            summary = response["message"]["content"].strip()
            summary = self._clean_summary(summary)
            return summary
            
        except Exception as e:
            print(f"[ProfileSummary] 生成画像摘要失败: {e}")
            return None

    def _clean_summary(self, text: str) -> str:
        import re
        text = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def get_or_create_profile(self, user_id: int) -> Dict[str, Any]:
        db = get_db()
        return get_or_create_user_profile(db, user_id)

    def should_regenerate(self, user_id: int, threshold: int = None) -> bool:
        threshold = threshold or self.token_threshold
        
        db = get_db()
        profile = get_user_profile(db, user_id)
        
        if not profile:
            return True
        
        current_tokens = self.calculate_conversation_tokens(user_id)
        saved_tokens = profile.get('total_tokens', 0) or 0
        
        return (current_tokens - saved_tokens) >= threshold

    def update_profile_summary(self, user_id: int) -> Optional[str]:
        db = get_db()
        
        summary = self.generate_profile_summary(user_id)
        if not summary:
            return None
        
        current_tokens = self.calculate_conversation_tokens(user_id)
        
        success = update_user_profile(db, user_id, summary, current_tokens)
        if success:
            print(f"[ProfileSummary] 用户 {user_id} 画像摘要已更新")
            return summary
        
        return None

    def get_profile_summary(self, user_id: int) -> Optional[str]:
        db = get_db()
        profile = get_user_profile(db, user_id)
        
        if profile and profile.get('profile_summary'):
            return profile['profile_summary']
        
        return None


_profile_summary_manager: Optional[ProfileSummaryManager] = None


def get_profile_summary_manager() -> ProfileSummaryManager:
    global _profile_summary_manager
    if _profile_summary_manager is None:
        _profile_summary_manager = ProfileSummaryManager()
    return _profile_summary_manager
