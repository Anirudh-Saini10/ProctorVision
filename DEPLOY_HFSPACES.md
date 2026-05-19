# Deploying ProctorVision on Hugging Face Spaces

Single Docker Space — frontend + backend + ML models, all from one container.

**Cost: $0** (HF Spaces free tier: 2 vCPU, 16 GB RAM, 50 GB disk).

---

## Prerequisites

1. Code on GitHub: `Anirudh-Saini10/ProctorVision`
2. Free [Hugging Face](https://huggingface.co) account
3. A PostgreSQL database URL (the existing Render DB works, or use [Neon](https://neon.tech/) free tier)

---

## Step-by-Step Deployment

### 1. Create the Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in:
   - **Owner**: your HF username
   - **Space name**: `proctorvision` (or any name)
   - **SDK**: **Docker**
   - **Hardware**: **CPU basic** (free)
   - **Visibility**: Public or Private (your choice)
3. Click **Create Space**

### 2. Connect to GitHub (Recommended)

Two options:

**Option A — Link GitHub repo directly:**
1. In the Space settings → **Repository** → connect your GitHub repo
2. HF Spaces will build on every push to `main`

**Option B — Push via HF Git:**
```bash
# Clone your new HF Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/proctorvision
cd proctorvision

# Add your code (copy from your GitHub repo or add as remote)
git remote add github https://github.com/Anirudh-Saini10/ProctorVision.git
git pull github main --allow-unrelated-histories

# Push to HF
git push origin main
```

### 3. Set Environment Variables

In the Space → **Settings** → **Variables and secrets**, add:

| Variable | Value | Type |
|----------|-------|------|
| `DATABASE_URL` | `postgresql+pg8000://user:pass@host/db` | Secret |
| `JWT_SECRET` | (any random string, e.g. `openssl rand -hex 32`) | Secret |
| `TF_CPP_MIN_LOG_LEVEL` | `3` | Variable |
| `PYTHONUNBUFFERED` | `1` | Variable |
| `YOLO_CONFIG_DIR` | `/tmp/ultralytics` | Variable |
| `ULTRALYTICS_DIR` | `/tmp/ultralytics` | Variable |

> **Note:** Use the same `DATABASE_URL` from your Render setup. It works from HF Spaces too (Render Postgres is publicly accessible).

### 4. Wait for Build

First build takes **~10-15 minutes** (downloading PyTorch, MediaPipe, YOLO model, building React frontend).

Watch the build logs in the Space's **Logs** tab.

### 5. Verify

Once the build is green:

1. Open `https://YOUR_USERNAME-proctorvision.hf.space` → you should see the React app
2. Check `https://YOUR_USERNAME-proctorvision.hf.space/api/health` → `{"status": "healthy"}`
3. Check `https://YOUR_USERNAME-proctorvision.hf.space/api/health/engine` → `{"ready": true, ...}`

---

## How It Works

The Dockerfile builds **everything** into one container:

```
┌──────────────────────────────────────────┐
│  Docker Container (port 7860)            │
│                                          │
│  ┌─────────────────────────────────────┐ │
│  │  FastAPI (uvicorn)                  │ │
│  │                                     │ │
│  │  /api/*    → REST endpoints         │ │
│  │  /ws       → candidate WebSocket    │ │
│  │  /ws/proctor → proctor WebSocket    │ │
│  │  /*        → React SPA (static)     │ │
│  └─────────────────────────────────────┘ │
│                                          │
│  Models: face_landmarker.task, yolov8n   │
│  DB: external PostgreSQL (Render/Neon)   │
└──────────────────────────────────────────┘
```

---

## Free Tier Notes

- **Sleep after inactivity**: HF Spaces free tier sleeps after ~15 min of no requests. First request after sleep takes ~30s to wake.
- **Keep warm**: Use [cron-job.org](https://cron-job.org) to ping `/api/health` every 10 min.
- **Ephemeral disk**: Local SQLite won't persist across restarts. Use external PostgreSQL (already configured).
- **No GPU needed**: YOLOv8n + MediaPipe run fine on CPU for single-user proctoring.

---

## Troubleshooting

**Build fails with OOM:**
- Free tier has enough RAM (16GB), but if it still fails, ensure `pip install --no-cache-dir` is used.

**`libGL.so.1` error persists:**
- The updated Dockerfile installs `libgl1-mesa-glx` which provides the full OpenGL runtime. If still failing, add `libgl1-mesa-dri` too.

**WebSocket won't connect:**
- Verify the URL uses `wss://` (not `ws://`). The updated `config.js` handles this automatically.
- HF Spaces proxy supports WebSockets natively.

**Database connection refused:**
- If using Render Postgres, ensure the DB allows external connections (Render free DBs are public by default).
- Check that `DATABASE_URL` is set in Space secrets.

**404 on frontend routes:**
- The SPA catch-all in `main.py` serves `index.html` for all non-API routes. Ensure the frontend built successfully (check build logs for npm errors).

---

## Updating

Push to `main` → HF Spaces auto-rebuilds. Code-only changes rebuild in ~2-3 min (dependencies cached).
