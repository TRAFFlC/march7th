import subprocess
import time
import requests
import os
import sys
import re
import io
import wave
import gc
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import config
from emotion_config import get_emotion_audio_path


_tts_start_lock = threading.Lock()


def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [TTS] {msg}", flush=True)


def clear_gpu_memory():
    try:
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                log("GPU显存已清理 (torch.cuda.empty_cache)")
        except ImportError:
            pass
    except Exception as e:
        log(f"GPU显存清理失败: {e}")


def clean_text_for_tts(text: str) -> str:
    text = re.sub(r'<think\b[^>]*>.*?</think\s*>', '',
                  text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\[EMOTION:[^\]]+\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[（(][^)）]*[)）]', '', text)
    text = re.sub(r'\*[^*]+\*', '', text)
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，、。？！,.?!]', ' ', text)

    allowed_punctuation = '，、。？！,、.?!'
    result = []
    for char in text:
        if char in allowed_punctuation:
            result.append(char)
        elif char in '；;\n':
            result.append('，')
        elif char in '：:':
            result.append('，')
        elif char in '…':
            result.append('。')
        elif char in '—－-':
            result.append('，')
        elif char in '～~':
            result.append('。')
        elif char in '"\'"\'「」『』【】':
            continue
        elif char.strip():
            result.append(char)

    cleaned = ''.join(result)
    cleaned = re.sub(r'\s+', '', cleaned)
    cleaned = re.sub(r'([，、。？！])+', r'\1', cleaned)
    cleaned = re.sub(r'^[，、。？！]+', '', cleaned)

    return cleaned.strip()


def split_text_by_punctuation(text: str, min_segments: int = 2) -> list:
    punctuation_pattern = r'([，、。？！])'
    parts = re.split(punctuation_pattern, text)
    segments = []
    current = ""
    punct_count = 0
    for part in parts:
        if not part:
            continue
        if re.match(punctuation_pattern, part):
            current += part
            punct_count += 1
            if punct_count >= min_segments:
                segments.append(current.strip())
                current = ""
                punct_count = 0
        else:
            current += part
    if current.strip():
        segments.append(current.strip())
    return [s for s in segments if s]


class TTSService:
    def __init__(
        self,
        gpt_path: str = None,
        sovits_path: str = None,
        ref_audio_path: str = None,
        ref_text: str = None,
        port: int = None,
    ):
        self.gpt_path = gpt_path or config.TTS_GPT_WEIGHT
        self.sovits_path = sovits_path or config.TTS_SOVITS_WEIGHT
        self.ref_audio_path = ref_audio_path or config.REF_AUDIO_PATH
        self.ref_text = ref_text or config.REF_AUDIO_TEXT
        self.port = port or config.TTS_PORT
        self.process = None
        self.api_dir = Path(config.GPT_SOVITS_DIR)
        self.runtime_python = self.api_dir / "runtime" / "python.exe"
        self._synthesize_lock = threading.Lock()
        self._running = False

    def update_ref_audio(self, ref_audio_path: str, ref_text: str = None):
        if ref_audio_path:
            self.ref_audio_path = ref_audio_path
        if ref_text:
            self.ref_text = ref_text

    def _get_emotion_audio_path(self, emotion: str, character_id: str) -> Tuple[Optional[str], Optional[str]]:
        if not emotion or emotion.lower() == "neutral":
            return self.ref_audio_path, self.ref_text
        return get_emotion_audio_path(character_id, emotion)

    def update_weights(self, gpt_path: str = None, sovits_path: str = None):
        if gpt_path:
            self.gpt_path = gpt_path
        if sovits_path:
            self.sovits_path = sovits_path

    def start(self, timeout: int = 120) -> bool:
        if self._is_running():
            log("TTS服务已在运行")
            self._running = True
            return True

        log(f"启动TTS API服务...")
        log(f"  GPT权重: {self.gpt_path}")
        log(f"  SoVITS权重: {self.sovits_path}")
        log(f"  参考音频: {self.ref_audio_path}")
        log(f"  参考文本: {self.ref_text}")

        if not Path(self.gpt_path).exists():
            log(f"错误: GPT权重文件不存在: {self.gpt_path}")
            return False
        if not Path(self.sovits_path).exists():
            log(f"错误: SoVITS权重文件不存在: {self.sovits_path}")
            return False
        if not Path(self.ref_audio_path).exists():
            log(f"错误: 参考音频文件不存在: {self.ref_audio_path}")
            return False

        if self.runtime_python.exists():
            python_exe = str(self.runtime_python)
            log(f"使用GPT-SoVITS便携Python: {python_exe}")
        else:
            python_exe = sys.executable
            log(f"使用系统Python: {python_exe}")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.api_dir)

        cmd = [
            python_exe,
            str(self.api_dir / "api.py"),
            "-s", self.sovits_path,
            "-g", self.gpt_path,
            "-dr", self.ref_audio_path,
            "-dt", self.ref_text,
            "-dl", "zh",
            "-d", "cuda",
            "-a", "127.0.0.1",
            "-p", str(self.port),
        ]

        log(f"执行命令: {' '.join(cmd[:5])}...")

        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.api_dir),
            env=env,
        )

        log(f"等待TTS服务就绪 (超时: {timeout}s)...")
        log("TTS进程输出将直接显示在控制台...")
        ready = self._wait_for_ready(timeout)
        if ready:
            log("TTS服务已就绪")
            self._running = True
        else:
            if self.process and self.process.poll() is None:
                log("TTS服务启动超时，但进程仍在运行，尝试继续...")
                self._running = True
            else:
                log("TTS服务启动失败，进程已退出")
        return self._running

    def _is_running(self) -> bool:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex(('127.0.0.1', self.port))
            if result == 0:
                log(f"端口 {self.port} 已开放")
                return True
            return False
        except Exception as e:
            log(f"端口检查异常: {e}")
            return False
        finally:
            sock.close()

    def _wait_for_ready(self, timeout: int = 120) -> bool:
        start_time = time.time()
        check_count = 0
        while time.time() - start_time < timeout:
            check_count += 1
            if self._is_running():
                log(f"TTS服务就绪 (检查次数: {check_count})")
                return True

            if self.process and self.process.poll() is not None:
                log(f"TTS进程退出，返回码: {self.process.returncode}")
                return False

            elapsed = int(time.time() - start_time)
            if elapsed > 0 and elapsed % 10 == 0:
                log(f"等待中... 已等待 {elapsed}s (检查次数: {check_count})")

            time.sleep(1)

        log(f"TTS服务启动超时 (总检查次数: {check_count})")
        return False

    def _synthesize_single(
        self,
        text: str,
        text_language: str = "zh",
        top_k: int = 15,
        top_p: float = 0.6,
        temperature: float = 0.6,
        speed: float = 1.0,
        split: bool = True,
    ) -> bytes:
        payload = {
            "text": text,
            "text_language": text_language,
            "refer_wav_path": self.ref_audio_path,
            "prompt_text": self.ref_text,
            "prompt_language": "zh",
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "speed": speed,
            "split": split,
        }

        log(f"调用 TTS API: text={text[:30]}..., split={split}")

        try:
            response = requests.post(
                f"http://127.0.0.1:{self.port}/",
                json=payload,
                timeout=120,
            )

            if response.status_code != 200:
                log(f"TTS合成失败: status={response.status_code}, response={response.text[:200]}")
                raise RuntimeError(f"TTS synthesis failed: {response.text}")

            log(f"TTS API 返回成功: {len(response.content)} bytes")
            return response.content
        except requests.exceptions.Timeout:
            log("TTS API 请求超时 (120s)")
            raise RuntimeError("TTS API request timeout")
        except requests.exceptions.ConnectionError as e:
            log(f"TTS API 连接错误: {e}")
            raise RuntimeError(f"TTS API connection error: {e}")

    def _merge_wav_audio(self, audio_chunks: list) -> bytes:
        if not audio_chunks:
            return b''
        if len(audio_chunks) == 1:
            return audio_chunks[0]

        output_buffer = io.BytesIO()
        output_wave = None
        params = None

        for i, chunk in enumerate(audio_chunks):
            chunk_buffer = io.BytesIO(chunk)
            with wave.open(chunk_buffer, 'rb') as wav_reader:
                if params is None:
                    params = wav_reader.getparams()
                    output_wave = wave.open(output_buffer, 'wb')
                    output_wave.setparams(params)
                frames = wav_reader.readframes(wav_reader.getnframes())
                output_wave.writeframes(frames)

        if output_wave:
            output_wave.close()

        return output_buffer.getvalue()

    def synthesize(
        self,
        text: str,
        text_language: str = "zh",
        top_k: int = 15,
        top_p: float = 0.6,
        temperature: float = 0.6,
        speed: float = 1.0,
        emotion: str = "neutral",
        character_id: str = None,
    ) -> bytes:
        log(f"synthesize 被调用, _running={self._running}, _synthesize_lock 获取中...")
        with self._synthesize_lock:
            if not self._is_running():
                log("TTS服务未运行，尝试重启...")
                if not self.start(timeout=60):
                    log("TTS服务重启失败")
                    return b''
                log("TTS服务重启成功")

            cleaned_text = clean_text_for_tts(text)
            if not cleaned_text:
                log("警告: 清洗后文本为空")
                return b''

            log(f"原始文本: {text[:50]}...")
            log(f"清洗后文本: {cleaned_text[:50]}...")

            original_ref_audio = None
            original_ref_text = None
            if character_id:
                emotion_ref_audio, emotion_ref_text = self._get_emotion_audio_path(
                    emotion, character_id)
                if emotion_ref_audio and emotion_ref_audio != self.ref_audio_path:
                    log(f"使用情感音频: {emotion} - {emotion_ref_audio}")
                    original_ref_audio = self.ref_audio_path
                    original_ref_text = self.ref_text
                    self.ref_audio_path = emotion_ref_audio
                    self.ref_text = emotion_ref_text or self.ref_text

            log(f"使用服务端按句切分功能，文本长度: {len(cleaned_text)}")

            try:
                audio_bytes = self._synthesize_single(
                    cleaned_text, text_language, top_k, top_p, temperature, speed, split=True
                )
            except Exception as e:
                log(f"合成失败: {e}")
                audio_bytes = b''

            if original_ref_audio:
                self.ref_audio_path = original_ref_audio
                self.ref_text = original_ref_text

            if not audio_bytes:
                return b''

            log(f"合成完成，总音频大小: {len(audio_bytes)} bytes")

            clear_gpu_memory()
            return audio_bytes

    def stop(self) -> bool:
        self._running = False
        if not self._is_running():
            self.process = None
            return True

        try:
            requests.get(
                f"http://127.0.0.1:{self.port}/control?command=exit", timeout=5)
        except:
            pass

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None

        clear_gpu_memory()
        return True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


_tts_instance: TTSService = None


def check_gpu_memory() -> float:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
                "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        else:
            return -1
    except subprocess.TimeoutExpired:
        return -1
    except FileNotFoundError:
        return -1
    except Exception as e:
        return -1


def wait_for_memory_release(threshold_mb: float = None, timeout: float = None) -> bool:
    threshold = threshold_mb or config.GPU_MEMORY_THRESHOLD
    max_wait = timeout or config.MAX_WAIT_TIME

    log(f"等待显存释放 (阈值: {threshold}MB, 超时: {max_wait}s)...")
    start_time = time.time()
    while time.time() - start_time < max_wait:
        memory = check_gpu_memory()
        if 0 <= memory < threshold:
            log(f"显存已释放: {memory:.0f}MB")
            return True
        time.sleep(config.MEMORY_CHECK_INTERVAL)
    log(f"显存释放超时，当前: {check_gpu_memory():.0f}MB")
    return False


def get_tts_instance(
    ref_audio_path: str = None,
    ref_text: str = None,
) -> TTSService:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSService(
            ref_audio_path=ref_audio_path,
            ref_text=ref_text,
        )
    elif ref_audio_path or ref_text:
        if ref_audio_path:
            _tts_instance.ref_audio_path = ref_audio_path
        if ref_text:
            _tts_instance.ref_text = ref_text
    return _tts_instance


def synthesize_speech(
    text: str,
    ref_audio_path: str = None,
    ref_text: str = None,
    text_language: str = "zh",
    top_k: int = 15,
    top_p: float = 0.6,
    temperature: float = 0.6,
    speed: float = 1.0,
    auto_start: bool = True,
    emotion: str = "neutral",
    character_id: str = None,
) -> bytes:
    global _tts_start_lock
    tts = get_tts_instance(ref_audio_path, ref_text)

    if auto_start and not tts._is_running():
        with _tts_start_lock:
            if not tts._is_running():
                log("TTS服务未运行，正在启动...")
                started = tts.start()
                if not started:
                    raise RuntimeError("TTS服务启动失败")

    return tts.synthesize(
        text=text,
        text_language=text_language,
        top_k=top_k,
        top_p=top_p,
        temperature=temperature,
        speed=speed,
        emotion=emotion,
        character_id=character_id,
    )


def get_current_ref_config() -> dict:
    return {
        "ref_audio_path": config.REF_AUDIO_PATH,
        "ref_text": config.REF_AUDIO_TEXT,
        "gpt_weight": config.TTS_GPT_WEIGHT,
        "sovits_weight": config.TTS_SOVITS_WEIGHT,
        "port": config.TTS_PORT,
    }
