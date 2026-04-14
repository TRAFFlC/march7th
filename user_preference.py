"""
用户偏好分析模块 - 基于jieba关键词提取
User Preference Analysis Module - Based on jieba keyword extraction
"""

import math
import jieba
import jieba.analyse
from typing import List, Dict, Tuple, Optional
from database import get_db, save_preference, get_preferences, get_preferences_with_decay, get_all_preferences_with_decay
from config import PREFERENCE_DECAY_RATE


STOP_WORDS = set([
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '什么', '他', '她', '它', '们', '这个', '那个', '怎么',
    '吗', '呢', '啊', '吧', '呀', '哦', '嗯', '哈', '嘿', '喂', '哇', '哎', '唉',
    '可以', '可能', '应该', '需要', '还是', '或者', '但是', '因为', '所以', '如果',
    '虽然', '不过', '而且', '然后', '接着', '最后', '首先', '其实', '确实',
])


def calculate_decayed_weight(count: int, days_ago: float, decay_rate: float = PREFERENCE_DECAY_RATE) -> float:
    return count * math.exp(-decay_rate * days_ago)


def get_preferences_with_decay_info(user_id: int, limit: int = 10, decay_rate: float = PREFERENCE_DECAY_RATE) -> List[Dict]:
    db = get_db()
    return get_all_preferences_with_decay(db, user_id, decay_rate, limit)


def extract_keywords(text: str, top_k: int = 5) -> List[Tuple[str, float]]:
    if not text or not text.strip():
        return []
    
    keywords = jieba.analyse.extract_tags(
        text,
        topK=top_k * 2,
        withWeight=True,
        allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an')
    )
    
    filtered = []
    for word, weight in keywords:
        if word.lower() not in STOP_WORDS and len(word) >= 2:
            filtered.append((word, weight))
        if len(filtered) >= top_k:
            break
    
    return filtered


def analyze_sentiment(text: str) -> str:
    if not text:
        return 'neutral'
    
    positive_words = {
        '喜欢', '爱', '好', '棒', '赞', '厉害', '优秀', '完美', '精彩', '有趣',
        '开心', '高兴', '快乐', '满意', '感谢', '谢谢', '太好了', '超棒', '超级',
        '可爱', '萌', '温柔', '贴心', '有趣', '有意思', '好玩', '厉害', '牛',
        '厉害', '强', '好棒', '太棒', '真棒', '很好', '真好', '不错', '挺好',
    }
    
    negative_words = {
        '讨厌', '烦', '无聊', '差', '烂', '垃圾', '糟糕', '不好', '不行', '不对',
        '错误', '失败', '失望', '难过', '伤心', '生气', '愤怒', '讨厌', '烦人',
        '无聊', '没意思', '太差', '很差', '太烂', '很烂', '不好', '不好用',
    }
    
    words = set(jieba.cut(text))
    
    positive_count = len(words & positive_words)
    negative_count = len(words & negative_words)
    
    if positive_count > negative_count:
        return 'positive'
    elif negative_count > positive_count:
        return 'negative'
    else:
        return 'neutral'


def extract_and_save_preferences(
    user_id: int,
    text: str,
    rating: int = None,
    top_k: int = 3,
) -> List[Dict]:
    if not text or not user_id:
        return []
    
    keywords = extract_keywords(text, top_k=top_k)
    if not keywords:
        return []
    
    sentiment = 'neutral'
    if rating is not None:
        if rating >= 4:
            sentiment = 'positive'
        elif rating <= 2:
            sentiment = 'negative'
    else:
        sentiment = analyze_sentiment(text)
    
    if sentiment == 'neutral':
        return []
    
    db = get_db()
    saved = []
    
    for word, weight in keywords:
        success = save_preference(db, user_id, word, sentiment)
        if success:
            saved.append({
                'keyword': word,
                'weight': weight,
                'sentiment': sentiment,
            })
    
    return saved


def get_user_preference_summary(user_id: int, limit: int = 5, decay_rate: float = PREFERENCE_DECAY_RATE) -> Dict:
    db = get_db()
    
    positive = get_preferences_with_decay(db, user_id, 'positive', decay_rate, limit)
    negative = get_preferences_with_decay(db, user_id, 'negative', decay_rate, limit)
    
    return {
        'positive_keywords': [
            {
                'keyword': p['keyword'], 
                'count': p['count'], 
                'effective_weight': p['decayed_weight'],
                'days_ago': p.get('days_ago', 0)
            } 
            for p in positive
        ],
        'negative_keywords': [
            {
                'keyword': n['keyword'], 
                'count': n['count'], 
                'effective_weight': n['decayed_weight'],
                'days_ago': n.get('days_ago', 0)
            } 
            for n in negative
        ],
    }


def build_preference_context(user_id: int, max_keywords: int = 5, decay_rate: float = PREFERENCE_DECAY_RATE) -> str:
    summary = get_user_preference_summary(user_id, max_keywords, decay_rate)
    
    context_parts = []
    
    if summary['positive_keywords']:
        pos_words = [f"{p['keyword']}({p['effective_weight']:.2f})" for p in summary['positive_keywords']]
        context_parts.append(f"用户喜欢的话题: {', '.join(pos_words)}")
    
    if summary['negative_keywords']:
        neg_words = [f"{n['keyword']}({n['effective_weight']:.2f})" for n in summary['negative_keywords']]
        context_parts.append(f"用户不喜欢的话题: {', '.join(neg_words)}")
    
    return '\n'.join(context_parts) if context_parts else ''


class UserPreferenceAnalyzer:
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        self._cache: Dict[int, Dict] = {}
    
    def set_user(self, user_id: int):
        self.user_id = user_id
    
    def analyze_input(self, text: str, rating: int = None) -> List[Dict]:
        if not self.user_id:
            return []
        return extract_and_save_preferences(self.user_id, text, rating)
    
    def get_context(self, max_keywords: int = 5, decay_rate: float = PREFERENCE_DECAY_RATE) -> str:
        if not self.user_id:
            return ''
        
        cache_key = f"{self.user_id}_{decay_rate}"
        if cache_key in self._cache:
            return self._cache[cache_key].get('context', '')
        
        context = build_preference_context(self.user_id, max_keywords, decay_rate)
        self._cache[cache_key] = {'context': context}
        return context
    
    def clear_cache(self):
        self._cache.clear()
    
    def refresh(self, decay_rate: float = PREFERENCE_DECAY_RATE):
        cache_key = f"{self.user_id}_{decay_rate}" if self.user_id else None
        if cache_key and cache_key in self._cache:
            del self._cache[cache_key]
        return self.get_context(decay_rate=decay_rate)


_preference_analyzer: Optional[UserPreferenceAnalyzer] = None


def get_preference_analyzer(user_id: int = None) -> UserPreferenceAnalyzer:
    global _preference_analyzer
    if _preference_analyzer is None:
        _preference_analyzer = UserPreferenceAnalyzer(user_id)
    elif user_id is not None:
        _preference_analyzer.set_user(user_id)
    return _preference_analyzer
