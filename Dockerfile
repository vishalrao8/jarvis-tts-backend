FROM python:3.11-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tar \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install standalone Piper Linux binary release
RUN mkdir -p /app/piper && \
    curl -sL https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz | tar -xz -C /app

# Download J.A.R.V.I.S. ONNX model and config from Hugging Face
RUN mkdir -p /app/model && \
    curl -sL https://huggingface.co/vishalrao8/piper-jarvis-high/resolve/main/en_GB-jarvis-high.onnx -o /app/model/en_GB-jarvis-high.onnx && \
    curl -sL https://huggingface.co/vishalrao8/piper-jarvis-high/resolve/main/en_GB-jarvis-high.onnx.json -o /app/model/en_GB-jarvis-high.onnx.json

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

ENV HOST=0.0.0.0
ENV PORT=8000
ENV PIPER_BIN=/app/piper/piper
ENV MODEL_PATH=/app/model/en_GB-jarvis-high.onnx
ENV CONFIG_PATH=/app/model/en_GB-jarvis-high.onnx.json

EXPOSE 8000

CMD ["python", "server.py"]
