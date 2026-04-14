import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


def _extract_json_from_response(response: str) -> str:
    """
    从 LLM 响应中提取 JSON 内容。
    处理 markdown 代码块包裹的情况，如 ```json ... ```
    """
    response = response.strip()
    
    pattern = r'^```(?:json)?\s*(.*?)\s*```$'
    match = re.match(pattern, response, re.DOTALL)
    if match:
        response = match.group(1).strip()
    elif response.startswith('```'):
        lines = response.split('\n')
        if len(lines) > 1:
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response = '\n'.join(lines).strip()
        else:
            if response.endswith('```'):
                response = response[3:-3].strip()
            elif response.startswith('```json'):
                response = response[6:].strip()
            else:
                response = response[3:].strip()
    
    response = response.strip()
    
    try:
        json.loads(response)
        return response
    except json.JSONDecodeError:
        pass
    
    if response.startswith('{'):
        depth = 0
        last_valid_pos = -1
        for i, char in enumerate(response):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    last_valid_pos = i
                    break
        
        if last_valid_pos > 0:
            candidate = response[:last_valid_pos + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
    
    if response.startswith('['):
        depth = 0
        last_valid_pos = -1
        for i, char in enumerate(response):
            if char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
                if depth == 0:
                    last_valid_pos = i
                    break
        
        if last_valid_pos > 0:
            candidate = response[:last_valid_pos + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
    
    return response


TEXT_FILE = Path(__file__).parent / "resources" / \
    "character_texts" / "march7th.txt"
OUTPUT_DIR = Path(__file__).parent / "resources" / "emotions" / "march7th"


def _get_emotion_prompt() -> str:
    from prompt_manager import get_prompt_manager
    return get_prompt_manager().get_raw_prompt("emotion_classification", "emotion_classification")

EMOTION_LABELS = ["happy", "confused", "sad", "angry", "excited", "neutral"]

EMOTION_KEYWORDS = {
    "happy": ["开心", "高兴", "快乐", "棒", "好开心", "太好了", "哈哈", "嘿嘿", "嘻嘻", "哇", "呀", "不错", "喜欢", "感谢", "谢谢", "棒棒", "完美", "超棒", "真棒"],
    "confused": ["奇怪", "怎么回事", "吗", "呢", "咦", "嗯", "到底", "为什么", "怎么", "是不是", "难道", "不清楚", "不明白", "不懂", "不知道", "迷惑", "疑问", "什么"],
    "sad": ["难过", "伤心", "痛苦", "悲伤", "遗憾", "可惜", "唉", "哎", "沮丧", "失落", "无奈", "可惜", "遗憾", "伤心", "悲观"],
    "angry": ["生气", "愤怒", "可恶", "讨厌", "过分", "气", "哼", "讨厌", "可恶", "坏人", "混蛋", "该死", "气人", "不爽", "过分"],
    "excited": ["哇", "哇哇", "太棒了", "激动", "兴奋", "厉害", "震撼", "惊人", "不可思议", "简直", "超", "超级", "非常", "极其", "简直了"],
    "neutral": []
}


class EmotionClassifier:
    def __init__(self, model_name: str = "uer/roberta-base-finetuned-jd-binary-chinese"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.tokenizer = None
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name, local_files_only=True)
            self.model.to(self.device)
            self.model.eval()
            print(f"[EmotionClassifier] 成功从本地缓存加载模型: {model_name}")
        except Exception as e:
            print(f"[EmotionClassifier] 本地缓存加载失败，尝试在线下载: {e}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                self.model.to(self.device)
                self.model.eval()
                print(f"[EmotionClassifier] 成功在线下载模型: {model_name}")
            except Exception as e2:
                print(f"[EmotionClassifier] 模型加载失败，将使用关键词模式: {e2}")
                self.model = None
                self.tokenizer = None

    def predict(self, text: str) -> str:
        if self.model is None or self.tokenizer is None:
            return self._keyword_based_predict(text)
        
        try:
            inputs = self.tokenizer(text, return_tensors="pt",
                                    truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                predicted_class = torch.argmax(logits, dim=1).item()

            sentiment = "positive" if predicted_class == 1 else "negative"
            return self._sentiment_to_emotion(text, sentiment)
        except Exception as e:
            print(f"[EmotionClassifier] 预测失败，使用关键词模式: {e}")
            return self._keyword_based_predict(text)
    
    def _keyword_based_predict(self, text: str) -> str:
        text_lower = text.lower()
        
        for emotion, keywords in EMOTION_KEYWORDS.items():
            if emotion == "neutral":
                continue
            for keyword in keywords:
                if keyword in text_lower:
                    return emotion
        
        if any(c in text for c in ["！", "哇", "呀", "哈哈", "嘿嘿"]):
            return "excited"
        if any(c in text for c in ["？", "嗯", "呢", "啊"]):
            return "confused"
        if any(c in text for c in ["唉", "哎", "可惜", "遗憾"]):
            return "sad"
        if "哼" in text or "讨厌" in text:
            return "angry"
        
        return "neutral"

    def _sentiment_to_emotion(self, text: str, sentiment: str) -> str:
        text_lower = text.lower()

        for emotion, keywords in EMOTION_KEYWORDS.items():
            if emotion == "neutral":
                continue
            for keyword in keywords:
                if keyword in text_lower:
                    return emotion

        if sentiment == "positive":
            if any(c in text for c in ["！", "哇", "呀", "哈哈", "嘿嘿"]):
                return "excited"
            return "happy"
        else:
            if any(c in text for c in ["？", "嗯", "呢", "啊"]):
                return "confused"
            if any(c in text for c in ["唉", "哎", "可惜", "遗憾"]):
                return "sad"
            if "哼" in text or "讨厌" in text:
                return "angry"
            return "neutral"


def load_dialogue_lines(file_path: Path) -> List[Tuple[int, str]]:
    lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                lines.append((i, line))
    return lines


def create_emotion_folders(base_dir: Path) -> None:
    for emotion in EMOTION_LABELS:
        emotion_dir = base_dir / emotion
        emotion_dir.mkdir(parents=True, exist_ok=True)


def classify_dialogue(
    classifier: EmotionClassifier,
    lines: List[Tuple[int, str]]
) -> Dict[str, List[Tuple[int, str]]]:
    classified: Dict[str, List[Tuple[int, str]]] = {
        e: [] for e in EMOTION_LABELS}

    for line_num, text in lines:
        emotion = classifier.predict(text)
        classified[emotion].append((line_num, text))

    return classified


def save_classification_results(
    output_dir: Path,
    classified: Dict[str, List[Tuple[int, str]]]
) -> None:
    result_file = output_dir / "classification_results.json"

    results = {}
    for emotion, items in classified.items():
        results[emotion] = [
            {"line": line_num, "text": text} for line_num, text in items
        ]

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"分类结果已保存到: {result_file}")

    for emotion, items in classified.items():
        emotion_dir = output_dir / emotion
        march7th_dir = emotion_dir / "march7th"
        march7th_dir.mkdir(parents=True, exist_ok=True)

        text_file = march7th_dir / "dialogues.txt"
        with open(text_file, "w", encoding="utf-8") as f:
            for line_num, text in items:
                f.write(f"{line_num}|{text}\n")

        print(f"  {emotion}: {len(items)} 条对话 -> {text_file}")


def print_statistics(classified: Dict[str, List[Tuple[int, str]]]) -> None:
    print("\n情绪分类统计:")
    print("-" * 40)
    total = sum(len(items) for items in classified.values())

    for emotion in EMOTION_LABELS:
        count = len(classified[emotion])
        percentage = (count / total * 100) if total > 0 else 0
        print(f"{emotion:10s}: {count:4d} ({percentage:5.1f}%)")


def main():
    print("=" * 50)
    print("三月七对话情绪分类工具")
    print("=" * 50)

    if not TEXT_FILE.exists():
        print(f"错误: 找不到文本文件 {TEXT_FILE}")
        return

    print(f"\n正在加载文本文件: {TEXT_FILE}")
    lines = load_dialogue_lines(TEXT_FILE)
    print(f"共加载 {len(lines)} 条对话")

    print("\n正在初始化情感分析模型...")
    try:
        classifier = EmotionClassifier()
        print("模型加载成功!")
    except Exception as e:
        print(f"模型加载失败: {e}")
        print("将使用基于规则的分类方法...")
        classifier = None

    print("\n正在创建情绪文件夹...")
    create_emotion_folders(OUTPUT_DIR)

    print("\n正在分类对话...")
    if classifier:
        classified = classify_dialogue(classifier, lines)
    else:
        classified = classify_dialogue_rule_based(lines)

    print_statistics(classified)

    print("\n正在保存分类结果...")
    save_classification_results(OUTPUT_DIR, classified)

    print("\n分类完成!")
    print(f"结果文件: {OUTPUT_DIR / 'classification_results.json'}")
    print(f"各情绪文件夹已创建在: {OUTPUT_DIR}")


def classify_dialogue_rule_based(lines: List[Tuple[int, str]]) -> Dict[str, List[Tuple[int, str]]]:
    classifier = EmotionClassifier()
    return classify_dialogue(classifier, lines)


EMOTION_CLASSIFICATION_PROMPT = ""


def _ensure_emotion_prompt():
    global EMOTION_CLASSIFICATION_PROMPT
    if not EMOTION_CLASSIFICATION_PROMPT:
        EMOTION_CLASSIFICATION_PROMPT = _get_emotion_prompt()


def get_emotion_api_config(character) -> Optional[Any]:
    if character is None:
        return None
    if character.emotion_api_config is not None:
        return character.emotion_api_config
    if character.api_config is not None:
        return character.api_config
    return None


class LLMEmotionClassifier:
    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider
        self._fallback_classifier = None
        try:
            from config import EMOTION_CLASSIFICATION_MODE
            self._mode = EMOTION_CLASSIFICATION_MODE
        except ImportError:
            self._mode = "keyword_hybrid"

    def _get_fallback(self):
        if self._fallback_classifier is None:
            try:
                self._fallback_classifier = EmotionClassifier()
            except Exception:
                self._fallback_classifier = None
        return self._fallback_classifier

    def predict(self, text: str) -> str:
        result = self.predict_detailed(text)
        return result.get("emotion", "neutral")

    def predict_detailed(self, text: str) -> Dict[str, Any]:
        if self._mode == "keyword_only":
            fallback = self._get_fallback()
            if fallback is not None:
                try:
                    emotion = fallback.predict(text)
                    return {"emotion": emotion, "confidence": 0.5, "reason": "keyword_only mode"}
                except Exception:
                    pass
            return {"emotion": "neutral", "confidence": 0.0, "reason": "keyword_only mode, no fallback available"}

        if self._mode == "llm_only":
            if self.llm_provider is not None:
                try:
                    return self._predict_with_llm(text)
                except Exception:
                    pass
            return {"emotion": "neutral", "confidence": 0.0, "reason": "llm_only mode, no llm available"}

        if self.llm_provider is not None:
            try:
                return self._predict_with_llm(text)
            except Exception:
                pass

        fallback = self._get_fallback()
        if fallback is not None:
            try:
                emotion = fallback.predict(text)
                return {"emotion": emotion, "confidence": 0.5, "reason": "keyword+model fallback"}
            except Exception:
                pass

        return {"emotion": "neutral", "confidence": 0.0, "reason": "no classifier available"}

    def _predict_with_llm(self, text: str) -> Dict[str, Any]:
        _ensure_emotion_prompt()
        prompt = EMOTION_CLASSIFICATION_PROMPT + text
        messages = [{"role": "user", "content": prompt}]
        result = self.llm_provider.generate(
            messages, temperature=0.1, top_p=0.9, max_tokens=256)
        content = result.get("content", "")

        try:
            extracted = _extract_json_from_response(content)
            parsed = json.loads(extracted)
            emotion = parsed.get("emotion", "neutral")
            if emotion not in EMOTION_LABELS:
                emotion = "neutral"
            return {
                "emotion": emotion,
                "confidence": float(parsed.get("confidence", 0.5)),
                "reason": parsed.get("reason", ""),
            }
        except (json.JSONDecodeError, ValueError):
            pass

        return {"emotion": "neutral", "confidence": 0.3, "reason": "llm output parse failed"}


if __name__ == "__main__":
    main()
