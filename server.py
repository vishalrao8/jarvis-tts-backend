#!/usr/bin/env python3
import os
import sys
import json
import struct
import subprocess
import urllib.parse
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

def make_wav_header(sample_rate=22050, channels=1, bits_per_sample=16, data_size=0x7fffffff):
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    riff_size = data_size + 36
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        min(riff_size, 0xffffffff),
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        min(data_size, 0xffffffff)
    )

class SynthesisHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _write_chunk(self, data):
        if not data:
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            return
        self.wfile.write(f"{len(data):X}\r\n".encode("latin1"))
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/health", "/"):
            resp = json.dumps({"status": "ready", "service": "jarvis-tts-api"}).encode("utf-8")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        if path == "/synthesize":
            params = urllib.parse.parse_qs(parsed.query)
            text = (params.get("text", [""])[0]).strip()
            length_scale = float(params.get("length_scale", [1.10])[0])
            noise_scale = float(params.get("noise_scale", [0.35])[0])
            noise_w = float(params.get("noise_w", [0.50])[0])

            if not text:
                err_resp = json.dumps({"error": "text query parameter required"}).encode("utf-8")
                self.send_response(400)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_resp)))
                self.end_headers()
                self.wfile.write(err_resp)
                return

            self.stream_synthesis(text, length_scale, noise_scale, noise_w)
            return

        err_resp = json.dumps({"error": "Not Found"}).encode("utf-8")
        self.send_response(404)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(err_resp)))
        self.end_headers()
        self.wfile.write(err_resp)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/synthesize":
            err_resp = json.dumps({"error": "Not Found"}).encode("utf-8")
            self.send_response(404)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_resp)))
            self.end_headers()
            self.wfile.write(err_resp)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
            text = data.get("text", "").strip()
            length_scale = float(data.get("length_scale", 1.10))
            noise_scale = float(data.get("noise_scale", 0.35))
            noise_w = float(data.get("noise_w", 0.50))

            if not text:
                err_resp = json.dumps({"error": "Text parameter is required."}).encode("utf-8")
                self.send_response(400)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_resp)))
                self.end_headers()
                self.wfile.write(err_resp)
                return

            self.stream_synthesis(text, length_scale, noise_scale, noise_w)

        except Exception as e:
            err_resp = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_resp)))
            self.end_headers()
            self.wfile.write(err_resp)

    def stream_synthesis(self, text, length_scale=1.10, noise_scale=0.35, noise_w=0.50):
        cmd = [
            PIPER_BIN,
            "--model", MODEL_PATH,
            "--config", CONFIG_PATH,
            "--noise_scale", str(noise_scale),
            "--length_scale", str(length_scale),
            "--noise_w", str(noise_w),
            "--sentence_silence", "0.22",
            "--output-raw"
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()

        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.end_headers()

        # 1. Send WAV header chunk immediately
        header = make_wav_header(sample_rate=22050, channels=1, bits_per_sample=16, data_size=0x7fffffff)
        self._write_chunk(header)

        # 2. Setup streaming Butterworth filter
        rate = 22050
        b, a = signal.butter(2, 9500 / (rate / 2), btype="low")
        zi = np.zeros(max(len(a), len(b)) - 1, dtype=np.float32)
        max_thresh = 32768.0 * 0.94

        # 3. Stream PCM audio as Piper generates it in real-time
        try:
            while True:
                raw_bytes = proc.stdout.read(4096)
                if not raw_bytes:
                    break
                pcm = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
                filtered, zi = signal.lfilter(b, a, pcm, zi=zi)
                peak = np.max(np.abs(filtered))
                if peak > max_thresh:
                    filtered = np.tanh(filtered / max_thresh) * max_thresh
                chunk_out = filtered.astype(np.int16).tobytes()
                self._write_chunk(chunk_out)

            self._write_chunk(b"")
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            proc.stdout.close()
            proc.wait()

def warmup_engine():
    try:
        cmd = [
            PIPER_BIN,
            "--model", MODEL_PATH,
            "--config", CONFIG_PATH,
            "--sentence_silence", "0.0",
            "--output-raw"
        ]
        subprocess.run(
            cmd,
            input=b"online",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10
        )
        print("Piper neural model pre-warmed into memory cache.")
    except Exception as e:
        print(f"Warmup notice: {e}")

def main():
    import threading
    threading.Thread(target=warmup_engine, daemon=True).start()
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
