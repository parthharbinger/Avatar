# DEPLOYMENT GUIDE — Real-Time Interactive AI Avatar Microservice

This guide provides end-to-end instructions for containerizing and deploying the Real-Time AI Avatar backend microservice to production environments (Docker, AWS, GCP, Render, Railway, Fly.io, DigitalOcean).

---

## 1. Quick Start with Docker & Docker Compose

### Prerequisites
- [Docker Engine](https://docs.docker.com/engine/install/) 20.10+
- [Docker Compose](https://docs.docker.com/compose/) v2.0+

### Step 1: Prepare Environment File
Create your production `.env` file from the template:
```bash
cp .env.example .env
```
Ensure your `.env` contains your production API keys:
```env
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO

SESSION_TIMEOUT_SECONDS=300
MAX_CONCURRENT_SESSIONS=50
CORS_ORIGINS=["https://yourdomain.com", "https://app.yourdomain.com"]

# LLM & Voice
GROQ_API_KEY=gsk_...
TTS_PROVIDER=edge-tts
EDGE_TTS_VOICE=en-US-JennyNeural

# WebRTC Video Providers (Configure any or all)
ANAM_API_KEY=...
DID_API_KEY=...
SIMLI_API_KEY=...
AKOOL_API_KEY=...
HEYGEN_API_KEY=...
```

### Step 2: Build & Start Containerized Microservice
```bash
# Build image and start in detached background mode
docker compose up -d --build
```

### Step 3: Verify Container Health
```bash
# Check container status
docker compose ps

# View real-time JSON logs
docker compose logs -f

# Verify health check endpoint
curl -s http://localhost:8000/health
```

Expected output:
```json
{
  "status": "ok",
  "environment": "production",
  "tts_provider": "edge-tts",
  "active_sessions": 0,
  "max_sessions": 50
}
```

---

## 2. Cloud Deployment Options

### Option A: Render.com (Easiest Cloud Deploy)

1. Create a **New Web Service** on [Render.com](https://render.com).
2. Connect your GitHub repository (`Avatar`).
3. Select **Docker** as the runtime environment.
4. Set the following environment variables in the Render Dashboard:
   - `ENVIRONMENT` = `production`
   - `PORT` = `8000`
   - `GROQ_API_KEY` = `gsk_...`
   - `ANAM_API_KEY` = `...`
   - `DID_API_KEY` = `...`
5. Set Health Check Path to `/health`.
6. Click **Create Web Service**. Render will automatically build the `Dockerfile` and provision an HTTPS/WSS domain (e.g. `https://avatar-api.onrender.com`).

---

### Option B: Fly.io (Global Edge Deployment)

1. Install Flyctl and authenticate:
   ```bash
   fly auth login
   ```
2. Launch the app in your `Avatar/` root:
   ```bash
   fly launch --no-deploy
   ```
3. Set secrets:
   ```bash
   fly secrets set GROQ_API_KEY="gsk_..." ANAM_API_KEY="..." DID_API_KEY="..."
   ```
4. Deploy:
   ```bash
   fly deploy
   ```

---

### Option C: Google Cloud Run (Serverless Container)

1. Build and push image to Google Artifact Registry:
   ```bash
   gcloud builds submit --tag gcr.io/[PROJECT-ID]/avatar-backend
   ```
2. Deploy to Cloud Run with HTTP/2 and WebSocket support:
   ```bash
   gcloud run deploy avatar-service \
     --image gcr.io/[PROJECT-ID]/avatar-backend \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --port 8000 \
     --set-env-vars ENVIRONMENT=production,GROQ_API_KEY=gsk_...
   ```

---

### Option D: AWS ECS / Fargate or EC2

1. **Build Multi-Platform Image**:
   ```bash
   docker buildx build --platform linux/amd64 -t [AWS_ACCOUNT_ID].dkr.ecr.[REGION].amazonaws.com/avatar:latest --push .
   ```
2. **ECS Task Definition**:
   - Memory: `1024 MB`, CPU: `512 (.5 vCPU)`
   - Port mappings: `8000/tcp`
   - Health check: `curl -f http://localhost:8000/health || exit 1`
3. **Application Load Balancer (ALB)**:
   - Enable **Stickiness** (cookie-based, 300s).
   - Target group protocol: `HTTP` on port `8000`.
   - ALB listener rules: HTTPS 443 with WebSocket Upgrade headers enabled.

---

## 3. Reverse Proxy & SSL Configuration (Nginx / Caddy)

When deploying behind an Nginx reverse proxy, ensure WebSocket upgrade headers are passed correctly so `ws://` and `wss://` connections persist without drops:

### Production `nginx.conf`:
```nginx
server {
    listen 80;
    server_name avatar.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name avatar.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/avatar.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/avatar.yourdomain.com/privkey.pem;

    # Timeouts for persistent WebSocket streams
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        # WebSocket Upgrade Headers (CRITICAL)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 4. Production Hardening & Scaling Checklist

- [x] **Zero Secrets in Docker Images**: Secrets are mounted at runtime via `.env` or cloud secret managers.
- [x] **Automated Session Cleanup**: Background task frees idle sessions after `SESSION_TIMEOUT_SECONDS` (300s).
- [x] **Concurrency Caps**: Protected against DDoS / runaway credit consumption via `MAX_CONCURRENT_SESSIONS` (default: 20-50).
- [x] **CORS Origins**: Restricted to authorized third-party domains in production.
- [x] **Automated Health Probes**: `/health` endpoint configured for ALB, Kubernetes, and Docker Compose healthchecks.
