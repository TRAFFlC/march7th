import json
import re
import threading
from typing import Dict, Any, Optional, List
from feedback_types import FeedbackType


def _get_rag_prompt(key: str) -> str:
    from prompt_manager import get_prompt_manager
    return get_prompt_manager().get_raw_prompt("rag_iteration", key)


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

FACT_ERROR_PROMPT = ""
ROLE_DEVIATION_PROMPT = ""
HISTORY_FORGET_PROMPT = ""
THINK_LEAK_ANALYSIS_PROMPT = ""


def _ensure_prompts():
    global FACT_ERROR_PROMPT, ROLE_DEVIATION_PROMPT, HISTORY_FORGET_PROMPT, THINK_LEAK_ANALYSIS_PROMPT
    if not FACT_ERROR_PROMPT:
        FACT_ERROR_PROMPT = _get_rag_prompt("fact_error")
        ROLE_DEVIATION_PROMPT = _get_rag_prompt("role_deviation")
        HISTORY_FORGET_PROMPT = _get_rag_prompt("history_forget")
        THINK_LEAK_ANALYSIS_PROMPT = _get_rag_prompt("think_leak")


def get_iteration_api_config(character) -> List[Any]:
    if character is None:
        return []

    configs = []

    if hasattr(character, 'iteration_apis') and character.iteration_apis:
        for api_dict in character.iteration_apis:
            if isinstance(api_dict, dict) and api_dict.get('provider_type', '') != 'ollama':
                from llm_provider import APIConfig as _APIConfig
                configs.append(_APIConfig(
                    provider_type=api_dict.get('provider_type', 'openai_compatible'),
                    base_url=api_dict.get('base_url', ''),
                    api_key=api_dict.get('api_key', ''),
                    model_name=api_dict.get('model_name', ''),
                ))

    if character.iteration_api_config is not None:
        if character.iteration_api_config.provider_type != 'ollama':
            already_added = any(
                c.base_url == character.iteration_api_config.base_url
                and c.model_name == character.iteration_api_config.model_name
                for c in configs
            )
            if not already_added:
                configs.append(character.iteration_api_config)

    if not configs and character.api_config is not None:
        if character.api_config.provider_type != 'ollama':
            configs.append(character.api_config)

    return configs


class RAGIterationManager:
    def __init__(self, llm_provider=None, llm_providers=None):
        self.llm_providers = llm_providers or []
        if llm_provider is not None and llm_provider not in self.llm_providers:
            self.llm_providers.insert(0, llm_provider)
        self.llm_provider = self.llm_providers[0] if self.llm_providers else None
        self._cancelled = threading.Event()
        _ensure_prompts()

    def cancel(self):
        self._cancelled.set()
        for provider in self.llm_providers:
            if hasattr(provider, 'cancel'):
                provider.cancel()

    def reset_cancel(self):
        self._cancelled.clear()
        for provider in self.llm_providers:
            if hasattr(provider, 'reset_cancel'):
                provider.reset_cancel()

    def _call_llm(self, prompt: str) -> str:
        if self._cancelled.is_set():
            raise Exception("Request cancelled due to timeout")
        if not self.llm_providers:
            raise Exception("未配置 LLM 提供商")

        messages = [{"role": "user", "content": prompt}]
        last_error = None

        for i, provider in enumerate(self.llm_providers):
            if self._cancelled.is_set():
                raise Exception("Request cancelled due to timeout")
            try:
                if hasattr(provider, 'reset_cancel'):
                    provider.reset_cancel()
                result = provider.generate(messages, temperature=0.3, top_p=0.9, max_tokens=1024)

                if self._cancelled.is_set():
                    raise Exception("Request cancelled due to timeout")

                if result.get("cancelled"):
                    raise Exception("Request cancelled due to timeout")

                if "error" in result and result["error"]:
                    last_error = Exception(result["error"])
                    print(f"[RAG Iteration] API #{i+1} 返回错误: {result['error']}, 尝试下一个配置...")
                    continue

                content = result.get("content", "")
                if not content:
                    last_error = Exception("API 返回空内容")
                    print(f"[RAG Iteration] API #{i+1} 返回空内容, 尝试下一个配置...")
                    continue

                if i > 0:
                    print(f"[RAG Iteration] API #{i+1} 成功响应")
                return content
            except Exception as e:
                if "cancelled" in str(e).lower() or "timeout" in str(e).lower():
                    raise
                last_error = e
                print(f"[RAG Iteration] API #{i+1} 请求异常: {e}, 尝试下一个配置...")
                continue

        raise last_error or Exception("所有 API 配置均失败")

    def export_context_for_fact_error(self, character_info: str, user_input: str,
                                       bot_reply: str, rag_results: List[Dict]) -> str:
        rag_text = "\n".join([f"[文档{r.get('index', i+1)}] 距离:{r.get('distance', 'N/A')}\n{r.get('content', '')}"
                             for i, r in enumerate(rag_results)])
        if not rag_text:
            rag_text = "无RAG检索结果"
        return FACT_ERROR_PROMPT.format(
            character_info=character_info,
            user_input=user_input,
            bot_reply=bot_reply,
            rag_results=rag_text
        )

    def export_context_for_role_deviation(self, character_info: str,
                                           user_input: str, bot_reply: str) -> str:
        return ROLE_DEVIATION_PROMPT.format(
            character_info=character_info,
            user_input=user_input,
            bot_reply=bot_reply
        )

    def export_context_for_history_forget(self, character_info: str,
                                           conversation_history: List[Dict],
                                           bot_reply: str) -> str:
        history_text = "\n".join([f"{'用户' if m['role']=='user' else '角色'}：{m['content']}"
                                  for m in conversation_history])
        return HISTORY_FORGET_PROMPT.format(
            character_info=character_info,
            conversation_history=history_text,
            bot_reply=bot_reply
        )

    def analyze_fact_error(self, character_info: str, user_input: str,
                           bot_reply: str, rag_results: List[Dict]) -> Dict[str, Any]:
        if self._cancelled.is_set():
            return {"error": "Request cancelled due to timeout", "cancelled": True}
        prompt = self.export_context_for_fact_error(character_info, user_input, bot_reply, rag_results)
        try:
            response = self._call_llm(prompt)
            if self._cancelled.is_set():
                return {"error": "Request cancelled due to timeout", "cancelled": True}
            return json.loads(_extract_json_from_response(response))
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_error": True}
        except Exception as e:
            return {"error": str(e), "api_error": True}

    def analyze_role_deviation(self, character_info: str, user_input: str,
                                bot_reply: str) -> Dict[str, Any]:
        if self._cancelled.is_set():
            return {"error": "Request cancelled due to timeout", "cancelled": True}
        prompt = self.export_context_for_role_deviation(character_info, user_input, bot_reply)
        try:
            response = self._call_llm(prompt)
            if self._cancelled.is_set():
                return {"error": "Request cancelled due to timeout", "cancelled": True}
            return json.loads(_extract_json_from_response(response))
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_error": True}
        except Exception as e:
            return {"error": str(e), "api_error": True}

    def analyze_history_forget(self, character_info: str, conversation_history: List[Dict],
                                bot_reply: str) -> Dict[str, Any]:
        if self._cancelled.is_set():
            return {"error": "Request cancelled due to timeout", "cancelled": True}
        prompt = self.export_context_for_history_forget(character_info, conversation_history, bot_reply)
        try:
            response = self._call_llm(prompt)
            if self._cancelled.is_set():
                return {"error": "Request cancelled due to timeout", "cancelled": True}
            return json.loads(_extract_json_from_response(response))
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_error": True}
        except Exception as e:
            return {"error": str(e), "api_error": True}

    def analyze_think_leak(self, bot_reply: str, model_name: str) -> Dict[str, Any]:
        if self._cancelled.is_set():
            return {"error": "Request cancelled due to timeout", "cancelled": True}
        prompt = THINK_LEAK_ANALYSIS_PROMPT.format(bot_reply=bot_reply, model_name=model_name)
        try:
            response = self._call_llm(prompt)
            if self._cancelled.is_set():
                return {"error": "Request cancelled due to timeout", "cancelled": True}
            return json.loads(_extract_json_from_response(response))
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_error": True}
        except Exception as e:
            return {"error": str(e), "api_error": True}

    def process_feedback(self, feedback_type: str, conversation_data: Dict[str, Any],
                         character_info: str = "", rag_results: List[Dict] = None,
                         conversation_history: List[Dict] = None) -> Dict[str, Any]:
        user_input = conversation_data.get("user_input", "")
        bot_reply = conversation_data.get("bot_reply", "")
        model_name = conversation_data.get("model_name", "")

        if feedback_type == FeedbackType.FACT_ERROR.value:
            return self.analyze_fact_error(character_info, user_input, bot_reply, rag_results or [])
        elif feedback_type == FeedbackType.ROLE_DEVIATION.value:
            return self.analyze_role_deviation(character_info, user_input, bot_reply)
        elif feedback_type == FeedbackType.HISTORY_FORGET.value:
            return self.analyze_history_forget(character_info, conversation_history or [], bot_reply)
        elif feedback_type == FeedbackType.THINK_LEAK.value:
            return self.analyze_think_leak(bot_reply, model_name)
        else:
            return self._analyze_general_feedback(feedback_type, conversation_data, character_info, rag_results, conversation_history)

    def _analyze_general_feedback(self, feedback_type: str, conversation_data: Dict[str, Any],
                                   character_info: str = "", rag_results: List[Dict] = None,
                                   conversation_history: List[Dict] = None) -> Dict[str, Any]:
        user_input = conversation_data.get("user_input", "")
        bot_reply = conversation_data.get("bot_reply", "")
        model_name = conversation_data.get("model_name", "")

        analyses = {}

        if self._detect_fact_error_indicators(user_input, bot_reply):
            analyses["fact_error"] = self.analyze_fact_error(character_info, user_input, bot_reply, rag_results or [])

        if self._detect_role_deviation_indicators(user_input, bot_reply, character_info):
            analyses["role_deviation"] = self.analyze_role_deviation(character_info, user_input, bot_reply)

        if conversation_history and len(conversation_history) > 0:
            if self._detect_history_forget_indicators(user_input, bot_reply, conversation_history):
                analyses["history_forget"] = self.analyze_history_forget(character_info, conversation_history, bot_reply)

        if self._detect_think_leak_indicators(bot_reply):
            analyses["think_leak"] = self.analyze_think_leak(bot_reply, model_name)

        if not analyses:
            analyses["general_analysis"] = self._perform_general_analysis(user_input, bot_reply, character_info)

        return {
            "feedback_type": feedback_type,
            "auto_detected": True,
            "analyses": analyses,
            "message": f"自动分析完成，检测到 {len(analyses)} 个潜在问题类型"
        }

    def _detect_fact_error_indicators(self, user_input: str, bot_reply: str) -> bool:
        fact_keywords = ["错误", "不对", "不是", "其实", "实际上", "搞错", "弄错", "事实", "真实"]
        combined = (user_input + bot_reply).lower()
        return any(kw in combined for kw in fact_keywords)

    def _detect_role_deviation_indicators(self, user_input: str, bot_reply: str, character_info: str) -> bool:
        deviation_keywords = ["不像", "不符合", "偏离", "性格", "人设", "角色", "风格"]
        combined = (user_input + bot_reply).lower()
        return any(kw in combined for kw in deviation_keywords)

    def _detect_history_forget_indicators(self, user_input: str, bot_reply: str, conversation_history: List[Dict]) -> bool:
        forget_keywords = ["忘了", "忘记", "之前说", "刚才", "上次", "已经", "不是第一次"]
        combined = (user_input + bot_reply).lower()
        return any(kw in combined for kw in forget_keywords)

    def _detect_think_leak_indicators(self, bot_reply: str) -> bool:
        leak_patterns = [
            "让我想想", "我来分析", "首先", "其次", "然后", "最后",
            "根据", "因为", "所以", "我认为", "我觉得", "思考",
            "步骤", "过程", "推理", "分析如下"
        ]
        return any(pattern in bot_reply for pattern in leak_patterns)

    def _perform_general_analysis(self, user_input: str, bot_reply: str, character_info: str) -> Dict[str, Any]:
        prompt = f"""你是一个角色扮演质量分析专家。请分析以下对话的质量问题。

## 角色信息
{character_info[:500] if character_info else '未提供角色信息'}

## 对话内容
用户：{user_input}
角色：{bot_reply}

请分析回答可能存在的问题。

## 输出要求
直接输出纯JSON，不要使用markdown代码块，不要输出任何其他内容。
格式：{{"potential_issues": [{{"type": "问题类型", "description": "问题描述", "suggestion": "改进建议"}}], "overall_quality": "good/medium/poor", "summary": "总体评价"}}"""

        try:
            response = self._call_llm(prompt)
            return json.loads(_extract_json_from_response(response))
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_error": True}
        except Exception as e:
            return {"error": str(e), "api_error": True}
