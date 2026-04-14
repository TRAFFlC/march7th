"""
三月七角色扮演推理接口 - RAG + Ollama
支持：混合BM25+向量搜索(RRF融合)、重复惩罚机制
"""
import config
import ollama
import chromadb
import re
import tiktoken
import math
import jieba
from collections import Counter
from sentence_transformers import SentenceTransformer
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from reranker import Reranker

import env_setup

MODEL_NAME = config.LLM_MODEL
RAG_DIR = Path(__file__).parent / "rag_db"
EMBEDDING_MODEL = config.EMBEDDING_MODEL

MAX_CONTEXT_TOKENS = 16384
OUTPUT_RESERVED = 500
MIN_OUTPUT_TOKENS = 100


def _get_inference_template(key: str) -> str:
    from prompt_manager import get_prompt_manager
    return get_prompt_manager().get_raw_prompt("inference_templates", key)


SIMPLE_SYSTEM_PROMPT = _get_inference_template("simple_system_prompt")


class BM25:
    def __init__(self, documents: List[str], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.doc_len = [len(list(jieba.cut(doc))) for doc in documents]
        self.avgdl = sum(self.doc_len) / len(documents) if documents else 1
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self._initialize()
    
    def _initialize(self):
        df = Counter()
        for doc in self.documents:
            words = set(jieba.cut(doc))
            freq = Counter(jieba.cut(doc))
            self.doc_freqs.append(dict(freq))
            df.update(words)
        
        N = len(self.documents)
        for word, freq in df.items():
            self.idf[word] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)
    
    def get_scores(self, query: str) -> List[float]:
        query_words = list(jieba.cut(query))
        scores = []
        
        for i, doc in enumerate(self.documents):
            score = 0.0
            doc_freq = self.doc_freqs[i]
            doc_len = self.doc_len[i]
            
            for word in query_words:
                if word not in doc_freq:
                    continue
                if word not in self.idf:
                    continue
                
                freq = doc_freq[word]
                idf = self.idf[word]
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator
            
            scores.append(score)
        
        return scores


def rrf_fusion(
    vector_results: List[Tuple[str, float]],
    bm25_results: List[Tuple[str, float]],
    k: int = 60,
    top_n: int = 5,
) -> List[Tuple[str, float, float, float]]:
    rrf_scores: Dict[str, float] = {}
    vector_ranks: Dict[str, int] = {}
    bm25_ranks: Dict[str, int] = {}
    
    for rank, (doc, _) in enumerate(vector_results, 1):
        vector_ranks[doc] = rank
        rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank)
    
    for rank, (doc, _) in enumerate(bm25_results, 1):
        bm25_ranks[doc] = rank
        rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank)
    
    sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    results = []
    for doc, rrf_score in sorted_docs:
        v_rank = vector_ranks.get(doc, 999)
        b_rank = bm25_ranks.get(doc, 999)
        results.append((doc, rrf_score, v_rank, b_rank))
    
    return results


def extract_repeat_phrases(history: List[dict], min_length: int = 4, min_count: int = 2) -> List[str]:
    if len(history) < 2:
        return []
    
    recent_responses = []
    for msg in history[-6:]:
        if msg.get('role') == 'assistant':
            recent_responses.append(msg.get('content', ''))
    
    if not recent_responses:
        return []
    
    phrase_counter = Counter()
    for response in recent_responses:
        words = list(jieba.cut(response))
        for i in range(len(words) - min_length + 1):
            phrase = ''.join(words[i:i + min_length])
            if len(phrase) >= min_length * 2 and not phrase.isspace():
                phrase_counter[phrase] += 1
    
    repeat_phrases = [phrase for phrase, count in phrase_counter.items() if count >= min_count]
    
    return repeat_phrases[:5]


def _format_persona_item(item: dict) -> str:
    doc = item.get("document", "")
    rating = item.get("rating", 0)
    reason = item.get("reason", "")

    text = f"[评分: {rating}/5]\n{doc}"
    if reason:
        text += f"\n用户评价原因: {reason}"
    return text


def _remove_think_tags(text: str) -> str:
    text = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL).strip()
    
    lines = text.split('\n')
    cleaned_lines = []
    skip_patterns = [
        r'^\s*[*\-+]\s*(Okay|So|The user|I should|Let me|I need to)',
        r'^\s*\d+\.\s*(Okay|So|The user|I should|Let me|I need to)',
        r'^\s*\(.*?(Internal|Monologue|Thinking|思考|分析|Evaluation).*?\)',
        r'^\s*.*?(Final (Decision|Output|Polish)|Selecting the best)',
        r'^\s*(See |Draft |Revised |Selecting )',
        r'^\s*\*\s{2,}',
        r'^\s*-{5,}$',
    ]
    
    for line in lines:
        should_skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                should_skip = True
                break
        if not should_skip:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()


def _parse_emotion_tag(text: str) -> tuple:
    pattern = r'\[EMOTION:\s*(\w+)\]'
    match = re.search(pattern, text)
    if match:
        emotion = match.group(1).lower()
        valid_emotions = {"happy", "confused", "sad", "angry", "excited", "neutral"}
        if emotion not in valid_emotions:
            emotion = "neutral"
        cleaned_text = re.sub(pattern, '', text).strip()
        return cleaned_text, emotion
    return text, "neutral"


class March7thChatbot:
    def __init__(
        self,
        use_rag: bool = True,
        top_k: int = 3,
        distance_threshold: float = 1.0,
        max_history_turns: int = 25,
        debug: bool = False,
        persona_manager=None,
        model_name: str = None,
        system_prompt: str = None,
        use_hybrid_search: bool = True,
        use_repeat_penalty: bool = True,
        use_rerank: bool = False,
        api_config=None,
        user_id: int = None,
        character_id: str = None,
        collection_name: str = "march7th_knowledge",
    ):
        self.use_rag = use_rag
        self.top_k = top_k
        self.distance_threshold = distance_threshold
        self.max_history_turns = max_history_turns
        self.debug = debug
        self.persona_manager = persona_manager
        self.model_name = model_name or MODEL_NAME
        self.system_prompt = system_prompt or SIMPLE_SYSTEM_PROMPT
        self.use_hybrid_search = use_hybrid_search
        self.use_repeat_penalty = use_repeat_penalty
        self.use_rerank = use_rerank
        self.api_config = api_config
        self.provider = None
        self.user_id = user_id
        self.character_id = character_id
        self.collection_name = collection_name

        if api_config is not None and api_config.provider_type != "ollama":
            from llm_provider import get_provider
            self.provider = get_provider(api_config)

        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.embedding_model = None
        self.collection = None
        self.all_documents: List[str] = []
        self.bm25_index: Optional[BM25] = None
        self.conversation_history: List[dict] = []
        self.rag_context_tokens = 0
        self._profile_summary: Optional[str] = None
        self.reranker = None
        self.character_config = None

        self._last_debug_info: dict = {}

    @property
    def is_api_mode(self):
        from llm_provider import OllamaProvider
        return self.provider is not None and not isinstance(self.provider, OllamaProvider)

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt or SIMPLE_SYSTEM_PROMPT

    def inject_profile_summary(self, profile_text: str):
        self._profile_summary = profile_text

    def compress_anchors(self, anchors: list, max_tokens: int = 500) -> str:
        total_chars = sum(len(a.get('content', '')) for a in anchors)
        estimated_tokens = total_chars // 4
        if estimated_tokens <= max_tokens:
            return "\n".join([f"[记忆锚点-{a.get('anchor_type', 'auto')}] {a.get('content', '')}" for a in anchors])

        if self.provider is not None:
            try:
                anchor_text = "\n".join([f"- {a.get('content', '')}" for a in anchors])
                prompt = f"请将以下记忆要点压缩为简洁的摘要，保留所有关键信息，不超过{max_tokens}个token：\n\n{anchor_text}"
                messages = [{"role": "user", "content": prompt}]
                result = self.provider.generate(messages, temperature=0.3, max_tokens=max_tokens)
                return result.get("content", "")
            except Exception:
                pass

        sorted_anchors = sorted(anchors, key=lambda x: x.get('importance', 0.5), reverse=True)
        selected = []
        current_chars = 0
        max_chars = max_tokens * 4
        for a in sorted_anchors:
            content = a.get('content', '')
            if current_chars + len(content) <= max_chars:
                selected.append(a)
                current_chars += len(content)
        return "\n".join([f"[记忆锚点-{a.get('anchor_type', 'auto')}] {a.get('content', '')}" for a in selected])

    def check_model(self):
        if self.is_api_mode:
            print(f"API 模式，跳过 Ollama 检查，使用模型: {self.model_name}")
            return
        try:
            ollama.list()
            print(f"Ollama 模型检查完成，使用模型: {self.model_name}")
        except Exception as e:
            raise ConnectionError(f"无法连接 Ollama: {e}")

    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))

    def _estimate_fixed_tokens(self, query: str, context: List[str] = None) -> int:
        tokens = self.count_tokens(
            self.system_prompt) + self.count_tokens(query)
        if context:
            tokens += self.count_tokens("\n\n".join(context))
        tokens += self.rag_context_tokens
        return tokens

    def get_context_usage(self) -> dict:
        history_tokens = sum(self.count_tokens(
            msg["content"]) for msg in self.conversation_history)
        return {
            "history_tokens": history_tokens,
            "max_context": MAX_CONTEXT_TOKENS,
            "usage_ratio": history_tokens / MAX_CONTEXT_TOKENS
        }

    def trim_history_by_tokens(self, max_tokens: int) -> int:
        if not self.conversation_history:
            return 0

        current_tokens = sum(self.count_tokens(
            msg["content"]) for msg in self.conversation_history)
        excess = current_tokens - max_tokens

        if excess <= 0:
            return 0

        removed_pairs = 0
        while excess > 0 and self.conversation_history:
            self.conversation_history.pop(0)
            if self.conversation_history:
                self.conversation_history.pop(0)
            removed_pairs += 1

            current_tokens = sum(self.count_tokens(
                msg["content"]) for msg in self.conversation_history)
            excess = current_tokens - max_tokens

        return removed_pairs

    def load_rag(self):
        if not self.use_rag or not RAG_DIR.exists():
            return

        if not self.collection_name:
            print("RAG 集合名称未配置，跳过 RAG 加载")
            return

        print(f"加载 RAG 知识库: {RAG_DIR}, 集合: {self.collection_name}")
        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL, device="cuda")
        client = chromadb.PersistentClient(path=str(RAG_DIR))

        try:
            self.collection = client.get_collection(self.collection_name)
        except Exception as e:
            print(f"RAG 集合 '{self.collection_name}' 不存在，跳过 RAG 加载: {e}")
            self.collection = None
            return

        if self.use_hybrid_search:
            print("构建 BM25 索引...")
            all_docs = self.collection.get(include=["documents"])
            self.all_documents = all_docs["documents"] if all_docs["documents"] else []
            if self.all_documents:
                self.bm25_index = BM25(self.all_documents)
                print(f"BM25 索引构建完成，共 {len(self.all_documents)} 个文档")

        print("RAG 知识库加载完成")

    def load_reranker(self):
        if not self.use_rerank:
            return
        print(f"加载 Reranker 模型: {config.RERANK_MODEL}")
        self.reranker = Reranker(model_name=config.RERANK_MODEL)
        print("Reranker 模型加载完成")

    def retrieve_context(self, query: str) -> tuple:
        if self.collection is None:
            return [], []

        query_embedding = self.embedding_model.encode([query])

        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=self.top_k * 2,
            include=["documents", "distances"]
        )

        documents = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results["distances"] else []

        if self.debug:
            print(f"\n[RAG Debug] 向量检索结果:")
            for i, (doc, dist) in enumerate(zip(documents[:self.top_k], distances[:self.top_k])):
                preview = doc[:50].replace(
                    '\n', ' ') + "..." if len(doc) > 50 else doc
                print(f"  [{i+1}] distance={dist:.4f}: {preview}")

        if self.use_hybrid_search and self.bm25_index is not None:
            bm25_scores = self.bm25_index.get_scores(query)
            bm25_results = list(zip(self.all_documents, bm25_scores))
            bm25_results = sorted(bm25_results, key=lambda x: x[1], reverse=True)[:self.top_k * 2]
            
            if self.debug:
                print(f"\n[RAG Debug] BM25 检索结果:")
                for i, (doc, score) in enumerate(bm25_results[:self.top_k]):
                    preview = doc[:50].replace('\n', ' ') + "..." if len(doc) > 50 else doc
                    print(f"  [{i+1}] score={score:.4f}: {preview}")
            
            vector_results = list(zip(documents, distances))
            fused_results = rrf_fusion(vector_results, bm25_results, top_n=self.top_k)
            
            if self.debug:
                print(f"\n[RAG Debug] RRF 融合结果:")
                for doc, rrf_score, v_rank, b_rank in fused_results:
                    preview = doc[:50].replace('\n', ' ') + "..." if len(doc) > 50 else doc
                    print(f"  RRF={rrf_score:.4f} (向量排名:{v_rank}, BM25排名:{b_rank}): {preview}")
            
            valid_docs = []
            valid_distances = []
            for doc, rrf_score, v_rank, b_rank in fused_results:
                for d, dist in zip(documents, distances):
                    if d == doc and dist < self.distance_threshold:
                        valid_docs.append(doc)
                        valid_distances.append(dist)
                        break

            if self.use_rerank and self.reranker is not None and valid_docs:
                reranked = self.reranker.rerank(query, valid_docs, top_k=config.RERANK_TOP_K)
                if reranked:
                    valid_docs = [doc for doc, _ in reranked]
                    valid_distances = valid_distances[:len(valid_docs)]

            return valid_docs, valid_distances

        valid_docs = []
        valid_distances = []
        for doc, dist in zip(documents, distances):
            if dist < self.distance_threshold:
                valid_docs.append(doc)
                valid_distances.append(dist)

        if self.use_rerank and self.reranker is not None and valid_docs:
            reranked = self.reranker.rerank(query, valid_docs, top_k=config.RERANK_TOP_K)
            if reranked:
                valid_docs = [doc for doc, _ in reranked]
                valid_distances = valid_distances[:len(valid_docs)]

        return valid_docs, valid_distances

    def _build_system_content(self, current_system_prompt: str, query: str, context: List[str], distances: List[float], positive_items: list, negative_items: list, rag_status: str) -> str:
        system_content = current_system_prompt

        if self.user_id is not None and self.character_id is not None:
            try:
                from database import get_memory_anchors, get_db
                db = get_db()
                anchors = get_memory_anchors(db, user_id=self.user_id, character_id=self.character_id)
                if anchors:
                    anchor_block = self.compress_anchors(anchors)
                    system_content += f"\n\n【重要记忆】\n{anchor_block}"
            except Exception:
                pass

        if rag_status == "no_results":
            system_content += "\n\n【重要】知识库中没有找到与用户问题相关的信息。请判断：如果是生活常识，可以正常回答；如果超出了你的知识范围，请根据「知识边界规则」做出困惑或好奇的反应，不要编造内容。"
        elif rag_status == "partial":
            system_content += "\n\n参考以下信息回答，若信息不足可灵活应对。"
        elif context:
            context_text = "\n\n".join(context)
            system_content += f"\n\n参考以下信息来回答用户问题：\n{context_text}"

        min_rating = config.PERSONA_MIN_RATING
        if positive_items:
            persona_text = "\n\n".join(_format_persona_item(item)
                                       for item in positive_items)
            system_content += _get_inference_template("persona_positive").format(
                min_rating=min_rating,
                persona_context=persona_text
            )

        if negative_items:
            negative_text = "\n\n".join(
                _format_persona_item(item) for item in negative_items)
            system_content += _get_inference_template("persona_negative").format(
                min_rating=min_rating,
                persona_context=negative_text
            )

        if self.use_repeat_penalty:
            repeat_phrases = extract_repeat_phrases(self.conversation_history)
            if repeat_phrases:
                phrases_text = "\n".join(f"- {phrase}" for phrase in repeat_phrases)
                system_content += _get_inference_template("repeat_penalty").format(repeat_phrases=phrases_text)
                if self.debug:
                    print(f"\n[Repeat Penalty] 检测到重复短语: {repeat_phrases}")

        if self._profile_summary:
            system_content += _get_inference_template("profile_summary").format(profile_summary=self._profile_summary)
            if self.debug:
                print(f"\n[Profile Summary] 已注入用户画像摘要")

        return system_content

    def _build_messages(self, system_content: str, query: str) -> List[dict]:
        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": query})

        import datetime
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 22:
            period = "evening"
        else:
            period = "night"

        if hasattr(self, 'character_config') and self.character_config:
            greeting = self.character_config.greeting_templates.get(period, "")
            if greeting:
                for msg in messages:
                    if msg.get('role') == 'system':
                        msg['content'] += f"\n\n【当前时段问候语】{greeting}"
                        break

        return messages

    def _trim_if_needed(self, messages: List[dict], system_content: str, query: str) -> tuple:
        input_tokens = sum(self.count_tokens(
            msg["content"]) for msg in messages)
        available_for_output = MAX_CONTEXT_TOKENS - input_tokens

        if available_for_output < MIN_OUTPUT_TOKENS:
            trim_target = MAX_CONTEXT_TOKENS - OUTPUT_RESERVED - MIN_OUTPUT_TOKENS
            self.trim_history_by_tokens(trim_target)

            messages = self._build_messages(system_content, query)
            input_tokens = sum(self.count_tokens(
                msg["content"]) for msg in messages)
            available_for_output = MAX_CONTEXT_TOKENS - input_tokens

        return messages, input_tokens, available_for_output

    def generate(
        self,
        query: str,
        max_new_tokens: int = 1024,
        temperature: float = 1.0,
        top_p: float = 0.9,
        model_name: str = None,
        system_prompt: str = None,
    ) -> dict:
        import time
        start_time = time.time()

        current_model = model_name or self.model_name
        current_system_prompt = system_prompt or self.system_prompt
        
        if 'qwen' in current_model.lower() and system_prompt is None:
            current_system_prompt = SIMPLE_SYSTEM_PROMPT
        
        context = []
        distances = []
        positive_items = []
        negative_items = []
        rag_status = "ok"

        if self.use_rag:
            context, distances = self.retrieve_context(query)

            if len(context) == 0:
                rag_status = "no_results"
            elif len(context) < self.top_k:
                rag_status = "partial"

        if self.persona_manager is not None:
            try:
                positive_items, negative_items = self.persona_manager.retrieve_persona_context(
                    query)
                if self.debug:
                    if positive_items:
                        print(
                            f"\n[Persona Debug] 检索到 {len(positive_items)} 条好评参考")
                    if negative_items:
                        print(
                            f"\n[Persona Debug] 检索到 {len(negative_items)} 条差评参考")
            except Exception as e:
                if self.debug:
                    print(f"\n[Persona Debug] 检索失败: {e}")
                positive_items = []
                negative_items = []

        system_content = self._build_system_content(
            current_system_prompt, query, context, distances,
            positive_items, negative_items, rag_status
        )
        messages = self._build_messages(system_content, query)
        messages, input_tokens, available_for_output = self._trim_if_needed(
            messages, system_content, query
        )

        safe_max_output = min(max_new_tokens, available_for_output -
                              OUTPUT_RESERVED, MAX_CONTEXT_TOKENS - input_tokens)

        if self.debug:
            usage = self.get_context_usage()
            print(
                f"\n[Token Debug] 输入: {input_tokens} | 可用输出: {available_for_output} | 实际输出限制: {safe_max_output}")
            print(
                f"[Token Debug] 历史使用: {usage['history_tokens']} / {usage['max_context']} ({usage['usage_ratio']:.1%})")

        if self.is_api_mode:
            provider_result = self.provider.generate(
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=safe_max_output,
            )

            raw_content = provider_result.get("content", "")
            provider_usage = provider_result.get("usage", {"input_tokens": 0, "output_tokens": 0})
            input_tokens = provider_usage.get("input_tokens", 0)
            output_tokens = provider_usage.get("output_tokens", 0)

            if provider_result.get("error"):
                raw_content = f"[ERROR] {provider_result['error']}"

            clean_content = _remove_think_tags(raw_content)
            clean_content, emotion = _parse_emotion_tag(clean_content)

            generation_time = time.time() - start_time

            rag_documents = []
            for i, (doc, dist) in enumerate(zip(context, distances)):
                rag_documents.append({
                    "index": i + 1,
                    "content": doc,
                    "distance": round(dist, 4),
                    "similarity": round(1 - dist, 4) if dist <= 1 else None,
                })

            self._last_debug_info = {
                "model": current_model,
                "query": query,
                "full_prompt": system_content,
                "messages": messages,
                "raw_output": raw_content,
                "clean_output": clean_content,
                "emotion": emotion,
                "tokens": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "raw_output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                "rag": {
                    "enabled": self.use_rag,
                    "status": rag_status,
                    "top_k": self.top_k,
                    "distance_threshold": self.distance_threshold,
                    "documents": rag_documents,
                },
                "persona": {
                    "positive_items": len(positive_items),
                    "negative_items": len(negative_items),
                },
                "generation_time": round(generation_time, 3),
                "temperature": temperature,
                "top_p": top_p,
            }

            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": clean_content})

            return {
                "response": clean_content,
                "emotion": emotion,
                "debug_info": self._last_debug_info,
            }

        response = ollama.chat(
            model=current_model,
            messages=messages,
            think=False,
            options={
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": safe_max_output,
            }
        )

        raw_content = response["message"]["content"]
        
        if not raw_content and 'qwen' in current_model.lower():
            if hasattr(response["message"], "thinking") and response["message"]["thinking"]:
                thinking = response["message"]["thinking"]
                lines = thinking.split('\n')
                content_lines = []
                in_content = False
                for line in lines:
                    if in_content or (line.strip() and not line.strip().startswith(('*', '-', '1.', '2.', '3.', '4.', '5.'))):
                        if line.strip() and not line.strip().startswith(('Thinking', '**', 'Process:', '---')):
                            in_content = True
                            content_lines.append(line)
                if content_lines:
                    raw_content = '\n'.join(content_lines).strip()
        
        clean_content = _remove_think_tags(raw_content)
        clean_content, emotion = _parse_emotion_tag(clean_content)

        output_tokens = self.count_tokens(clean_content)
        raw_output_tokens = self.count_tokens(raw_content)
        generation_time = time.time() - start_time

        rag_documents = []
        for i, (doc, dist) in enumerate(zip(context, distances)):
            rag_documents.append({
                "index": i + 1,
                "content": doc,
                "distance": round(dist, 4),
                "similarity": round(1 - dist, 4) if dist <= 1 else None,
            })

        self._last_debug_info = {
            "model": current_model,
            "query": query,
            "full_prompt": system_content,
            "messages": messages,
            "raw_output": raw_content,
            "clean_output": clean_content,
            "emotion": emotion,
            "tokens": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "raw_output_tokens": raw_output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "rag": {
                "enabled": self.use_rag,
                "status": rag_status,
                "top_k": self.top_k,
                "distance_threshold": self.distance_threshold,
                "documents": rag_documents,
            },
            "persona": {
                "positive_items": len(positive_items),
                "negative_items": len(negative_items),
            },
            "generation_time": round(generation_time, 3),
            "temperature": temperature,
            "top_p": top_p,
        }

        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append(
            {"role": "assistant", "content": clean_content})

        return {
            "response": clean_content,
            "emotion": emotion,
            "debug_info": self._last_debug_info,
        }

    def _prepare_messages_for_generation(
        self,
        query: str,
        model_name: str = None,
        system_prompt: str = None,
    ) -> tuple:
        current_model = model_name or self.model_name
        current_system_prompt = system_prompt or self.system_prompt
        
        if 'qwen' in current_model.lower() and system_prompt is None:
            current_system_prompt = SIMPLE_SYSTEM_PROMPT
        
        context = []
        distances = []
        positive_items = []
        negative_items = []
        rag_status = "ok"

        if self.use_rag:
            context, distances = self.retrieve_context(query)

            if len(context) == 0:
                rag_status = "no_results"
            elif len(context) < self.top_k:
                rag_status = "partial"

        if self.persona_manager is not None:
            try:
                positive_items, negative_items = self.persona_manager.retrieve_persona_context(
                    query)
            except Exception as e:
                if self.debug:
                    print(f"\n[Persona Debug] 检索失败: {e}")
                positive_items = []
                negative_items = []

        system_content = self._build_system_content(
            current_system_prompt, query, context, distances,
            positive_items, negative_items, rag_status
        )
        messages = self._build_messages(system_content, query)
        messages, input_tokens, available_for_output = self._trim_if_needed(
            messages, system_content, query
        )

        safe_max_output = min(1024, available_for_output -
                              OUTPUT_RESERVED, MAX_CONTEXT_TOKENS - input_tokens)

        rag_documents = []
        for i, (doc, dist) in enumerate(zip(context, distances)):
            rag_documents.append({
                "index": i + 1,
                "content": doc,
                "distance": round(dist, 4),
                "similarity": round(1 - dist, 4) if dist <= 1 else None,
            })

        debug_info = {
            "model": current_model,
            "query": query,
            "full_prompt": system_content,
            "messages": messages,
            "rag": {
                "enabled": self.use_rag,
                "status": rag_status,
                "top_k": self.top_k,
                "distance_threshold": self.distance_threshold,
                "documents": rag_documents,
            },
            "persona": {
                "positive_items": len(positive_items),
                "negative_items": len(negative_items),
            },
            "input_tokens": input_tokens,
        }

        return messages, safe_max_output, current_model, debug_info

    def generate_stream(
        self,
        query: str,
        temperature: float = 1.0,
        top_p: float = 0.9,
        model_name: str = None,
        system_prompt: str = None,
    ):
        messages, safe_max_output, current_model, debug_info = self._prepare_messages_for_generation(
            query, model_name, system_prompt
        )

        full_response = ""
        raw_content = ""

        try:
            if self.is_api_mode:
                for content in self.provider.generate_stream(
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=safe_max_output,
                ):
                    raw_content += content
                    full_response += content
                    yield content

                clean_content = _remove_think_tags(raw_content)
                clean_content, emotion = _parse_emotion_tag(clean_content)
                if clean_content != full_response:
                    full_response = clean_content

                self.conversation_history.append({"role": "user", "content": query})
                self.conversation_history.append({"role": "assistant", "content": full_response})

                self._last_debug_info = debug_info
                self._last_debug_info["raw_output"] = raw_content
                self._last_debug_info["clean_output"] = full_response
                self._last_debug_info["emotion"] = emotion
                self._last_debug_info["output_tokens"] = self.count_tokens(full_response)

                yield f"[EMOTION: {emotion}]"
                return

            stream = ollama.chat(
                model=current_model,
                messages=messages,
                stream=True,
                think=False,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": safe_max_output,
                }
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    raw_content += content
                    full_response += content
                    yield content

            clean_content = _remove_think_tags(raw_content)
            clean_content, emotion = _parse_emotion_tag(clean_content)
            if clean_content != full_response:
                full_response = clean_content

            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": full_response})

            self._last_debug_info = debug_info
            self._last_debug_info["raw_output"] = raw_content
            self._last_debug_info["clean_output"] = full_response
            self._last_debug_info["emotion"] = emotion
            self._last_debug_info["output_tokens"] = self.count_tokens(full_response)

            yield f"[EMOTION: {emotion}]"

        except Exception as e:
            yield f"[ERROR] {str(e)}"

    def get_last_debug_info(self) -> dict:
        return self._last_debug_info.copy()

    def clear_history(self):
        self.conversation_history = []

    def add_to_history(self, user_input: str, assistant_response: str):
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": assistant_response})

    def load_history_from_db(self, session_id: str, user_id: int = None) -> bool:
        from database import get_db, get_session, get_session_conversations

        db = get_db()
        session = get_session(db, session_id)
        if not session:
            if self.debug:
                print(f"[History] 会话不存在: {session_id}")
            return False

        if user_id is not None and session['user_id'] != user_id:
            if self.debug:
                print(f"[History] 无权访问会话: {session_id}")
            return False

        conversations = get_session_conversations(db, session_id)
        if not conversations:
            if self.debug:
                print(f"[History] 会话无历史记录: {session_id}")
            return True

        self.conversation_history = []

        for conv in conversations:
            self.conversation_history.append({"role": "user", "content": conv['user_input']})
            self.conversation_history.append({"role": "assistant", "content": conv['bot_reply']})

        if self.debug:
            print(f"[History] 已从数据库加载 {len(self.conversation_history)} 条消息到上下文")

        return True

    def load_messages_from_list(self, messages: List[dict]):
        self.conversation_history = []
        for msg in messages:
            if msg.get('role') in ('user', 'assistant'):
                self.conversation_history.append({
                    "role": msg['role'],
                    "content": msg.get('content', '')
                })

    def get_history_length(self) -> int:
        return len(self.conversation_history) // 2

    def chat(self):
        print("\n" + "=" * 50)
        print("三月七角色扮演对话系统")
        print("输入 'quit' 或 'exit' 退出")
        print("输入 'clear' 清除对话历史")
        print("=" * 50 + "\n")

        self.check_model()
        self.load_rag()
        self.load_reranker()

        while True:
            try:
                query = input("开拓者: ").strip()

                if query.lower() in ["quit", "exit", "q"]:
                    print("\n三月七: 哎，这么快就走啦？下次再来找我聊天哦！")
                    break

                if query.lower() in ["clear", "reset"]:
                    self.clear_history()
                    print("\n三月七: 好的！本姑娘把之前的聊天都忘光光啦，我们重新开始吧！\n")
                    continue

                if not query:
                    continue

                result = self.generate(query)
                print(f"\n三月七: {result['response']}\n")

            except KeyboardInterrupt:
                print("\n\n三月七: 哎呀，被吓到了...下次再见啦！")
                break


def main():
    import argparse
    parser = argparse.ArgumentParser(description="三月七角色扮演对话系统")
    parser.add_argument("--no-rag", action="store_true", help="禁用 RAG")
    parser.add_argument("--top-k", type=int, default=3, help="RAG 检索数量")
    parser.add_argument("--threshold", type=float,
                        default=0.888, help="RAG 距离阈值（越小越严格）")
    parser.add_argument("--debug", action="store_true", help="显示 RAG 检索调试信息")
    parser.add_argument("--test", type=str, help="测试单次对话")
    args = parser.parse_args()

    chatbot = March7thChatbot(
        use_rag=not args.no_rag,
        top_k=args.top_k,
        distance_threshold=args.threshold,
        debug=args.debug
    )

    if args.test:
        chatbot.check_model()
        chatbot.load_rag()
        result = chatbot.generate(args.test)
        print(f"三月七: {result['response']}")
    else:
        chatbot.chat()


if __name__ == "__main__":
    main()
