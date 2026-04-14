#!/usr/bin/env python3
"""
Sherpa-ONNX 唤醒词检测服务
通过 stdout JSON 输出提供唤醒词检测结果
"""

import sys
import os
import json
import time
import signal
import atexit

try:
    import sherpa_onnx
except ImportError:
    print(json.dumps({"status": "error", "message": "sherpa_onnx not installed. Run: pip install sherpa-onnx"}), flush=True)
    sys.exit(1)

try:
    import sounddevice as sd
except ImportError:
    print(json.dumps({"status": "error", "message": "sounddevice not installed. Run: pip install sounddevice"}), flush=True)
    sys.exit(1)

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
_running = True

def signal_handler(signum, frame):
    global _running
    _running = False
    print(json.dumps({"status": "stopping", "message": "Received stop signal"}), flush=True)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
atexit.register(lambda: signal_handler(0, None))

def create_kws():
    encoder_path = os.path.join(MODELS_DIR, "encoder.onnx")
    decoder_path = os.path.join(MODELS_DIR, "decoder.onnx")
    joiner_path = os.path.join(MODELS_DIR, "joiner.onnx")
    tokens_path = os.path.join(MODELS_DIR, "tokens.txt")
    keywords_path = os.path.join(MODELS_DIR, "keywords.txt")

    if not os.path.exists(encoder_path):
        return None, f"Model files not found in {MODELS_DIR}"

    if not os.path.exists(keywords_path):
        with open(keywords_path, "w", encoding="utf-8") as f:
            f.write("s ān y uè q ī @三月七\n")

    kws = sherpa_onnx.KeywordSpotter(
        encoder=encoder_path,
        decoder=decoder_path,
        joiner=joiner_path,
        tokens=tokens_path,
        keywords_file=keywords_path,
        num_threads=4,
        provider="cpu",
        keywords_score=1.5,
        keywords_threshold=0.25,
    )

    return kws, None

def main():
    kws, error = create_kws()
    if error:
        print(json.dumps({"status": "error", "message": error}), flush=True)
        return

    stream = kws.create_stream()
    print(json.dumps({"status": "ready", "message": "KWS initialized successfully"}), flush=True)

    sample_rate = 16000

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(json.dumps({"status": "audio_error", "message": str(status)}), flush=True)
            return

        samples = indata[:, 0].astype("float32")
        stream.accept_waveform(sample_rate, samples)

        while kws.is_ready(stream):
            kws.decode_stream(stream)

        result = kws.get_result(stream)
        if result:
            print(json.dumps({"status": "detected", "keyword": result}), flush=True)
            kws.reset_stream(stream)

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=512,
            callback=audio_callback
        ):
            print(json.dumps({"status": "listening", "message": "Listening for wake word..."}), flush=True)

            while _running:
                time.sleep(0.1)

    except KeyboardInterrupt:
        print(json.dumps({"status": "stopped", "message": "Stopped by user"}), flush=True)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), flush=True)
    finally:
        print(json.dumps({"status": "stopped", "message": "Microphone released"}), flush=True)

if __name__ == "__main__":
    main()
