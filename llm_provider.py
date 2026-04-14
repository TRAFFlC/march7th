import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator, List, Dict, Any, Optional


class BaseLLMProvider(ABC):

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        pass


class OllamaProvider(BaseLLMProvider):

    def __init__(self, model_name: str = "deepseek-r1:8b"):
        self.model_name = model_name

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        import ollama

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                think=False,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_tokens,
                },
            )

            content = response.get("message", {}).get("content", "")
            usage = {}

            if "prompt_eval_count" in response:
                usage["input_tokens"] = response.get("prompt_eval_count", 0)
                usage["output_tokens"] = response.get("eval_count", 0)
            else:
                usage["input_tokens"] = 0
                usage["output_tokens"] = 0

            return {
                "content": content,
                "usage": usage,
            }
        except Exception as e:
            return {
                "content": "",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "error": str(e),
            }

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> Generator[str, None, None]:
        import ollama

        try:
            stream = ollama.chat(
                model=self.model_name,
                messages=messages,
                stream=True,
                think=False,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_tokens,
                },
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    if content:
                        yield content
        except Exception as e:
            yield f"[ERROR] {str(e)}"

    def test_connection(self) -> Dict[str, Any]:
        import ollama

        start_time = time.time()
        try:
            ollama.list()
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": True,
                "message": f"Ollama 连接成功，模型: {self.model_name}",
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "message": f"Ollama 连接失败: {str(e)}",
                "latency_ms": round(latency_ms, 2),
            }


class OpenAICompatibleProvider(BaseLLMProvider):

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._http_client = None

    def _get_http_client(self):
        if self._http_client is not None:
            return self._http_client

        try:
            import httpx
            self._http_client = httpx
        except ImportError:
            import requests
            self._http_client = requests

        return self._http_client

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _calculate_retry_delay(
        self, attempt: int, response_headers: Optional[Dict[str, str]] = None
    ) -> float:
        max_delay = 30.0
        if response_headers:
            retry_after = response_headers.get("Retry-After") or response_headers.get(
                "retry-after"
            )
            if retry_after:
                try:
                    delay = float(retry_after)
                    print(f"[OpenAI Compatible] 检测到 Retry-After 头: {delay}秒")
                    return min(delay, max_delay)
                except ValueError:
                    pass
        delay = self.retry_delay * (2**attempt)
        delay = min(delay, max_delay)
        print(f"[OpenAI Compatible] 指数退避计算: 第{attempt + 1}次重试, 等待{delay}秒")
        return delay

    def _is_rate_limited(self, response) -> bool:
        if hasattr(response, "status_code"):
            return response.status_code == 429
        return False

    def _build_body(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        stream: bool = False,
    ) -> Dict[str, Any]:
        body = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if stream:
            body["stream"] = True
        return body

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        client = self._get_http_client()
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, temperature, top_p, max_tokens)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                if hasattr(client, "post") and not hasattr(client, "Client"):
                    response = client.post(url, headers=headers, json=body, timeout=120.0)
                    if self._is_rate_limited(response):
                        print(f"[OpenAI Compatible] 收到 429 状态码 (速率限制), 尝试次数: {attempt + 1}/{self.max_retries + 1}")
                        if attempt < self.max_retries:
                            delay = self._calculate_retry_delay(attempt, dict(response.headers))
                            print(f"[OpenAI Compatible] 等待 {delay} 秒后重试...")
                            time.sleep(delay)
                            continue
                        else:
                            return {
                                "content": "",
                                "usage": {"input_tokens": 0, "output_tokens": 0},
                                "error": "API 请求频率超限，已达到最大重试次数，请稍后再试",
                            }
                    response_json = response.json()
                else:
                    with client.Client(timeout=120.0) as http_client:
                        resp = http_client.post(url, headers=headers, json=body)
                        if self._is_rate_limited(resp):
                            print(f"[OpenAI Compatible] 收到 429 状态码 (速率限制), 尝试次数: {attempt + 1}/{self.max_retries + 1}")
                            if attempt < self.max_retries:
                                delay = self._calculate_retry_delay(attempt, dict(resp.headers))
                                print(f"[OpenAI Compatible] 等待 {delay} 秒后重试...")
                                time.sleep(delay)
                                continue
                            else:
                                return {
                                    "content": "",
                                    "usage": {"input_tokens": 0, "output_tokens": 0},
                                    "error": "API 请求频率超限，已达到最大重试次数，请稍后再试",
                                }
                        response_json = resp.json()

                print(f"[OpenAI Compatible] API响应: {json.dumps(response_json, ensure_ascii=False)[:500]}...")

                content = ""
                usage = {"input_tokens": 0, "output_tokens": 0}

                choices = response_json.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    print(f"[OpenAI Compatible] 提取到内容长度: {len(content)} 字符")

                resp_usage = response_json.get("usage", {})
                print(f"[OpenAI Compatible] usage字段: {resp_usage}")
                if resp_usage:
                    usage["input_tokens"] = resp_usage.get("prompt_tokens", 0)
                    usage["output_tokens"] = resp_usage.get("completion_tokens", 0)
                    if usage["input_tokens"] == 0 and usage["output_tokens"] == 0:
                        print(f"[OpenAI Compatible] 警告: usage字段存在但token计数为0")
                else:
                    print(f"[OpenAI Compatible] 警告: API响应中没有usage字段")

                return {
                    "content": content,
                    "usage": usage,
                }
            except Exception as e:
                last_error = e
                print(f"[OpenAI Compatible] 请求异常: {e}, 尝试次数: {attempt + 1}/{self.max_retries + 1}")
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    print(f"[OpenAI Compatible] 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    continue

        return {
            "content": "",
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "error": f"请求失败，已达到最大重试次数: {str(last_error)}",
        }

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> Generator[str, None, None]:
        client = self._get_http_client()
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        body = self._build_body(messages, temperature, top_p, max_tokens, stream=True)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                if hasattr(client, "post") and not hasattr(client, "Client"):
                    response = client.post(
                        url, headers=headers, json=body, stream=True, timeout=120.0
                    )
                    if self._is_rate_limited(response):
                        print(f"[OpenAI Compatible] 流式请求收到 429 状态码 (速率限制), 尝试次数: {attempt + 1}/{self.max_retries + 1}")
                        if attempt < self.max_retries:
                            delay = self._calculate_retry_delay(attempt, dict(response.headers))
                            print(f"[OpenAI Compatible] 等待 {delay} 秒后重试...")
                            time.sleep(delay)
                            continue
                        else:
                            yield "[ERROR] API 请求频率超限，已达到最大重试次数，请稍后再试"
                            return
                    for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.strip() == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
                    return
                else:
                    with client.Client(timeout=120.0) as http_client:
                        with http_client.stream(
                            "POST", url, headers=headers, json=body
                        ) as resp:
                            if self._is_rate_limited(resp):
                                print(f"[OpenAI Compatible] 流式请求收到 429 状态码 (速率限制), 尝试次数: {attempt + 1}/{self.max_retries + 1}")
                                if attempt < self.max_retries:
                                    delay = self._calculate_retry_delay(attempt, dict(resp.headers))
                                    print(f"[OpenAI Compatible] 等待 {delay} 秒后重试...")
                                    time.sleep(delay)
                                    continue
                                else:
                                    yield "[ERROR] API 请求频率超限，已达到最大重试次数，请稍后再试"
                                    return
                            for line in resp.iter_lines():
                                if not line:
                                    continue
                                if line.startswith("data: "):
                                    data = line[6:]
                                    if data.strip() == "[DONE]":
                                        return
                                    try:
                                        chunk = json.loads(data)
                                        choices = chunk.get("choices", [])
                                        if choices:
                                            delta = choices[0].get("delta", {})
                                            content = delta.get("content", "")
                                            if content:
                                                yield content
                                    except json.JSONDecodeError:
                                        continue
                    return
            except Exception as e:
                last_error = e
                print(f"[OpenAI Compatible] 流式请求异常: {e}, 尝试次数: {attempt + 1}/{self.max_retries + 1}")
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    print(f"[OpenAI Compatible] 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    continue

        yield f"[ERROR] 请求失败，已达到最大重试次数: {str(last_error)}"

    def test_connection(self) -> Dict[str, Any]:
        client = self._get_http_client()
        url = f"{self.base_url}/models"
        headers = self._build_headers()

        start_time = time.time()
        try:
            if hasattr(client, "get") and not hasattr(client, "Client"):
                response = client.get(url, headers=headers, timeout=10.0)
            else:
                with client.Client(timeout=10.0) as http_client:
                    response = http_client.get(url, headers=headers)

            latency_ms = (time.time() - start_time) * 1000

            if hasattr(response, "status_code"):
                status = response.status_code
            else:
                status = response.status_code

            if status == 200:
                return {
                    "success": True,
                    "message": f"API 连接成功，模型: {self.model_name}",
                    "latency_ms": round(latency_ms, 2),
                }
            else:
                return {
                    "success": False,
                    "message": f"API 返回状态码: {status}",
                    "latency_ms": round(latency_ms, 2),
                }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "message": f"API 连接失败: {str(e)}",
                "latency_ms": round(latency_ms, 2),
            }


@dataclass
class APIConfig:
    provider_type: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""


def get_provider(api_config: APIConfig) -> BaseLLMProvider:
    if api_config.provider_type == "ollama":
        return OllamaProvider(model_name=api_config.model_name)
    elif api_config.provider_type == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=api_config.base_url,
            api_key=api_config.api_key,
            model_name=api_config.model_name,
        )
    else:
        raise ValueError(f"不支持的 provider_type: {api_config.provider_type}")
