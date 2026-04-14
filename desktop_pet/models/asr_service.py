#!/usr/bin/env python3
"""
Sherpa-ONNX 离线语音识别服务
使用 streaming transducer 模型进行实时语音识别
"""

import sys
import os
import json
import time
import signal
import atexit
import queue

try:
    import sherpa_onnx
except ImportError:
    print(json.dumps({"status": "error", "message": "sherpa_onnx not installed"}), flush=True)
    sys.exit(1)

try:
    import sounddevice as sd
except ImportError:
    print(json.dumps({"status": "error", "message": "sounddevice not installed"}), flush=True)
    sys.exit(1)

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
ASR_MODEL_DIR = os.path.join(MODELS_DIR, "asr_model")
_running = True
_audio_queue = queue.Queue()

def signal_handler(signum, frame):
    global _running
    _running = False
    print(json.dumps({"status": "stopping", "message": "Received stop signal"}), flush=True)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
atexit.register(lambda: signal_handler(0, None))

def create_recognizer():
    if os.path.exists(ASR_MODEL_DIR):
        encoder_path = os.path.join(ASR_MODEL_DIR, "encoder-epoch-99-avg-1.onnx")
        decoder_path = os.path.join(ASR_MODEL_DIR, "decoder-epoch-99-avg-1.onnx")
        joiner_path = os.path.join(ASR_MODEL_DIR, "joiner-epoch-99-avg-1.onnx")
        tokens_path = os.path.join(ASR_MODEL_DIR, "tokens.txt")
        
        if not os.path.exists(encoder_path):
            return None, f"ASR model files not found in {ASR_MODEL_DIR}. Please run: python download_asr_model.py"
        
        recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=tokens_path,
            encoder=encoder_path,
            decoder=decoder_path,
            joiner=joiner_path,
            num_threads=4,
            provider="cpu",
            decoding_method="greedy_search",
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=20.0,
        )
        
        return recognizer, None
    else:
        encoder_path = os.path.join(MODELS_DIR, "encoder.onnx")
        decoder_path = os.path.join(MODELS_DIR, "decoder.onnx")
        joiner_path = os.path.join(MODELS_DIR, "joiner.onnx")
        tokens_path = os.path.join(MODELS_DIR, "tokens.txt")
        
        if not os.path.exists(encoder_path):
            return None, f"Model files not found. Please run: python download_asr_model.py"
        
        recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=tokens_path,
            encoder=encoder_path,
            decoder=decoder_path,
            joiner=joiner_path,
            num_threads=4,
            provider="cpu",
            decoding_method="greedy_search",
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=20.0,
        )
        
        return recognizer, None

def main():
    recognizer, error = create_recognizer()
    if error:
        print(json.dumps({"status": "error", "message": error}), flush=True)
        return
    
    stream = recognizer.create_stream()
    print(json.dumps({"status": "ready", "message": "ASR initialized successfully"}), flush=True)
    
    sample_rate = 16000
    audio_chunk_count = 0
    
    def audio_callback(indata, frames, time_info, status):
        nonlocal audio_chunk_count
        if status:
            print(json.dumps({"status": "audio_error", "message": str(status)}), flush=True)
            return
        audio_chunk_count += 1
        samples = indata[:, 0].astype("float32")
        _audio_queue.put(samples)
        if audio_chunk_count % 100 == 0:
            print(json.dumps({"status": "debug", "message": f"Received {audio_chunk_count} audio chunks"}), flush=True)
    
    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=512,
            callback=audio_callback
        ):
            print(json.dumps({"status": "listening", "message": "Listening for speech..."}), flush=True)
            
            while _running:
                try:
                    samples = _audio_queue.get(timeout=0.1)
                except:
                    continue
                
                stream.accept_waveform(sample_rate, samples)
                
                while recognizer.is_ready(stream):
                    recognizer.decode_stream(stream)
                
                result = recognizer.get_result(stream)
                
                if result:
                    print(json.dumps({"status": "partial", "text": result}), flush=True)
                
                if recognizer.is_endpoint(stream):
                    if result:
                        print(json.dumps({"status": "final", "text": result}), flush=True)
                    recognizer.reset(stream)
                    
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), flush=True)
    finally:
        print(json.dumps({"status": "stopped", "message": "ASR stopped"}), flush=True)

if __name__ == "__main__":
    main()
