# J.A.R.V.I.S. Cloud Synthesis API

Standalone neural speech synthesis backend for J.A.R.V.I.S. voice models (Piper TTS).
Containerized and ready for deployment on **Google Cloud Run**, **Render.com**, **Railway**, or any Docker host.

---

## Deploy to Google Cloud Run (Mumbai / asia-south1)

A preconfigured deployment script is provided:

```bash
chmod +x deploy.sh
./deploy.sh
```

This builds the multi-platform image (`linux/amd64`), pushes it to Google Artifact Registry in Mumbai, and deploys it as a serverless container on Cloud Run.

---

## Deploy to Render (Free Web Service)

1. Fork or push this repository to your GitHub account (e.g. `https://github.com/vishalrao8/jarvis-tts-backend`).
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** and select **Web Service**.
4. Connect this GitHub repository.
5. Render detects the `Dockerfile` automatically:
   - **Environment:** Docker
   - **Plan:** Free (512 MB RAM)
   - **Health Check Path:** `/health`
6. Click **Deploy Web Service**.
7. Once deployed, Render provides your permanent HTTPS URL (e.g. `https://jarvis-tts-api.onrender.com`).

---

## API Endpoints

### 1. Health Check
- **Method:** `GET /health`
- **Response:**
  ```json
  {
    "status": "ready",
    "service": "jarvis-tts-api"
  }
  ```

### 2. Synthesize Speech
- **Method:** `POST /synthesize`
- **Headers:** `Content-Type: application/json`
- **Body:**
  ```json
  {
    "text": "Good evening, sir. Subsystem telemetry is operational.",
    "length_scale": 1.10,
    "noise_scale": 0.35,
    "noise_w": 0.50
  }
  ```
- **Response:** Streaming `audio/wav` binary stream (22050 Hz, 16-bit mono).
- **CORS:** Enabled with `Access-Control-Allow-Origin: *` for web frontends.

---

## Local Development (Docker)

```bash
docker build -t jarvis-tts-api .
docker run -p 8000:8000 jarvis-tts-api
```
