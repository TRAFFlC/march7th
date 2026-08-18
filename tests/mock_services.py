"""
Mock services for testing without real Ollama or GPT-SoVITS
用于测试的模拟服务，无需真实的 Ollama 或 GPT-SoVITS
"""
import struct
import io
from typing import Generator, Dict, Any, List


class MockOllamaService:
    """模拟 Ollama LLM 服务"""

    DEFAULT_RESPONSE = "嘿嘿！本姑娘收到你的消息啦~ 这是一个模拟回复，用于测试目的。"

    def __init__(self, model: str = "mock-model"):
        self.model = model
        self.call_count = 0

    def mock_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        options: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        模拟 ollama.chat() 响应格式

        Args:
            messages: 对话消息列表
            model: 模型名称
            options: 生成选项 (temperature, top_p, num_predict 等)

        Returns:
            模拟的 ollama.chat 响应字典
        """
        self.call_count += 1

        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        response_text = self._generate_mock_response(user_message)

        return {
            "model": model or self.model,
            "created_at": "2024-01-01T00:00:00Z",
            "message": {
                "role": "assistant",
                "content": response_text,
            },
            "done": True,
            "total_duration": 1000000000,
            "load_duration": 100000000,
            "prompt_eval_count": len(user_message) // 2,
            "prompt_eval_duration": 500000000,
            "eval_count": len(response_text) // 2,
            "eval_duration": 500000000,
        }

    def mock_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        options: Dict[str, Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        模拟流式响应，逐块返回文本

        Yields:
            模拟的流式响应块
        """
        self.call_count += 1

        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        response_text = self._generate_mock_response(user_message)
        chunk_size = 5

        for i in range(0, len(response_text), chunk_size):
            chunk_text = response_text[i : i + chunk_size]
            is_done = i + chunk_size >= len(response_text)

            yield {
                "model": model or self.model,
                "created_at": "2024-01-01T00:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": chunk_text,
                },
                "done": is_done,
            }

    def _generate_mock_response(self, user_input: str) -> str:
        """根据用户输入生成模拟回复"""
        if "你好" in user_input or "hello" in user_input.lower():
            return "你好呀！本姑娘是三月七~ 很高兴见到你！"
        elif "名字" in user_input or "是谁" in user_input:
            return "本姑娘叫三月七！是星穹列车的乘客，也是你的伙伴哦~"
        elif "天气" in user_input:
            return "天气？本姑娘正在列车上呢，不过听说太空中的星星超级漂亮！"
        else:
            return self.DEFAULT_RESPONSE


class MockTTSService:
    """模拟 TTS 语音合成服务"""

    SAMPLE_RATE = 22050
    NUM_CHANNELS = 1
    SAMPLE_WIDTH = 2

    def __init__(self):
        self.call_count = 0

    def mock_synthesize(
        self,
        text: str,
        text_language: str = "zh",
        **kwargs,
    ) -> bytes:
        """
        模拟 TTS 合成，返回空的 WAV 音频字节

        Args:
            text: 要合成的文本
            text_language: 文本语言
            **kwargs: 其他 TTS 参数 (top_k, top_p, temperature, speed 等)

        Returns:
            最小有效 WAV 文件的字节
        """
        self.call_count += 1
        return create_minimal_wav_bytes()

    def mock_synthesize_with_silence(
        self,
        text: str,
        duration_seconds: float = 0.1,
        **kwargs,
    ) -> bytes:
        """
        模拟 TTS 合成，返回指定时长的静音 WAV

        Args:
            text: 要合成的文本
            duration_seconds: 静音时长（秒）

        Returns:
            包含静音数据的 WAV 文件字节
        """
        self.call_count += 1
        return create_silent_wav_bytes(duration_seconds)


def create_minimal_wav_bytes() -> bytes:
    """
    创建最小有效 WAV 文件字节（44字节头 + 0字节数据）

    WAV 文件格式：
    - RIFF header (12 bytes)
    - fmt chunk (24 bytes)
    - data chunk header (8 bytes)
    Total: 44 bytes header + audio data

    Returns:
        最小有效 WAV 文件的字节
    """
    num_samples = 0
    num_channels = 1
    sample_width = 2
    sample_rate = 22050

    byte_rate = sample_rate * num_channels * sample_width
    block_align = num_channels * sample_width
    data_size = num_samples * sample_width

    buffer = io.BytesIO()

    buffer.write(b"RIFF")
    buffer.write(struct.pack("<I", 36 + data_size))
    buffer.write(b"WAVE")

    buffer.write(b"fmt ")
    buffer.write(struct.pack("<I", 16))
    buffer.write(struct.pack("<H", 1))
    buffer.write(struct.pack("<H", num_channels))
    buffer.write(struct.pack("<I", sample_rate))
    buffer.write(struct.pack("<I", byte_rate))
    buffer.write(struct.pack("<H", block_align))
    buffer.write(struct.pack("<H", sample_width * 8))

    buffer.write(b"data")
    buffer.write(struct.pack("<I", data_size))

    return buffer.getvalue()


def create_silent_wav_bytes(duration_seconds: float = 0.1) -> bytes:
    """
    创建包含静音数据的 WAV 文件字节

    Args:
        duration_seconds: 静音时长（秒）

    Returns:
        包含静音数据的 WAV 文件字节
    """
    num_channels = 1
    sample_width = 2
    sample_rate = 22050

    num_samples = int(sample_rate * duration_seconds)
    byte_rate = sample_rate * num_channels * sample_width
    block_align = num_channels * sample_width
    data_size = num_samples * sample_width

    buffer = io.BytesIO()

    buffer.write(b"RIFF")
    buffer.write(struct.pack("<I", 36 + data_size))
    buffer.write(b"WAVE")

    buffer.write(b"fmt ")
    buffer.write(struct.pack("<I", 16))
    buffer.write(struct.pack("<H", 1))
    buffer.write(struct.pack("<H", num_channels))
    buffer.write(struct.pack("<I", sample_rate))
    buffer.write(struct.pack("<I", byte_rate))
    buffer.write(struct.pack("<H", block_align))
    buffer.write(struct.pack("<H", sample_width * 8))

    buffer.write(b"data")
    buffer.write(struct.pack("<I", data_size))

    silent_samples = b"\x00\x00" * num_samples
    buffer.write(silent_samples)

    return buffer.getvalue()


def get_mock_llm_response(query: str) -> str:
    """
    获取模拟 LLM 响应文本

    Args:
        query: 用户查询

    Returns:
        模拟的响应文本
    """
    service = MockOllamaService()
    response = service.mock_chat(messages=[{"role": "user", "content": query}])
    return response["message"]["content"]


def get_mock_tts_audio(text: str) -> bytes:
    """
    获取模拟 TTS 音频字节

    Args:
        text: 要合成的文本

    Returns:
        最小有效 WAV 文件的字节
    """
    return create_minimal_wav_bytes()


def get_mock_tts_audio_with_silence(text: str, duration_seconds: float = 0.1) -> bytes:
    """
    获取包含静音数据的模拟 TTS 音频字节

    Args:
        text: 要合成的文本
        duration_seconds: 静音时长（秒）

    Returns:
        包含静音数据的 WAV 文件字节
    """
    return create_silent_wav_bytes(duration_seconds)
