#!/usr/bin/env python3
import os
import sys
import json
import wave
import subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import numpy as np
from scipy import signal

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def find_file(env_name, candidates):
    if env_name in os.environ and os.path.exists(os.environ[env_name]):
        return os.environ[env_name]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

PIPER_BIN = find_file("PIPER_BIN", [
    "/app/piper/piper",
    os.path.join(BASE_DIR, "piper", "piper"),
    "piper"
])

MODEL_PATH = find_file("MODEL_PATH", [
    "/app/model/en_GB-jarvis-high.onnx",
    os.path.join(BASE_DIR, "model", "en_GB-jarvis-high.onnx"),
])

CONFIG_PATH = find_file("CONFIG_PATH", [
    "/app/model/en_GB-jarvis-high.onnx.json",
    os.path.join(BASE_DIR, "model", "en_GB-jarvis-high.onnx.json"),
])

def level_audio(samples, rate=22050):
    b, a = signal.butter(2, 9500 / (rate / 2), btype="low")
    filtered = signal.lfilter(b, a, samples)

    max_thresh = 32768.0 * 0.94
    peak = np.max(np.abs(filtered))
    if peak > max_thresh:
        filtered = np.tanh(filtered / max_thresh) * max_thresh
    elif peak > 0:
        filtered = filtered * (max_thresh / max(peak, 28000.0))

    return filtered

class SynthesisHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ready", "service": "jarvis-tts-api"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/synthesize":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
            text = data.get("text", "").strip()
            length_scale = str(data.get("length_scale", 1.10))
            noise_scale = str(data.get("noise_scale", 0.35))
            noise_w = str(data.get("noise_w", 0.50))

            if not text:
                self.send_response(400)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Text parameter is required."}).encode("utf-8"))
                return

            cmd = [
                PIPER_BIN,
                "--model", MODEL_PATH,
                "--config", CONFIG_PATH,
                "--noise_scale", noise_scale,
                "--length_scale", length_scale,
                "--noise_w", noise_w,
                "--sentence_silence", "0.22",
                "--output-raw"
            ]

            proc = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, check=True)
            raw_pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32)

            if len(raw_pcm) == 0:
                raise RuntimeError("Synthesized audio stream was empty.")

            processed_pcm = level_audio(raw_pcm, rate=22050)
            final_bytes = processed_pcm.astype(np.int16).tobytes()

            import io
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(final_bytes)

            wav_data = wav_buffer.getvalue()

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_data)))
            self.end_headers()
            self.wfile.write(wav_data)

        except Exception as e:
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

def main():
    server = ThreadingHTTPServer((HOST, PORT), SynthesisHandler)
    print(f"J.A.R.V.I.S. Cloud Synthesis API listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
