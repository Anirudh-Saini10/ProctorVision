# Deploying ProctorVision

Single-service deployment on **Render**. The frontend is built into the backend during deployment, and FastAPI serves both the React app and the API from the same origin.

Total monthly cost at portfolio scale: **$0**.

---

## Prerequisites

1. The code is on GitHub. Your repo: `Anirudh-Saini10/ProctorVision`.
2. Commit `backend/yolov8n.pt` to the repo (it's ~6 MB) so the model is available at boot. If `.gitignore` excludes it, remove that line and `git add backend/yolov8n.pt`.
3. Free account on [render.com](https://render.com) (GitHub sign-in)

---

## Deployment Steps

### Option A: Blueprint (recommended, one-click)

1. In Render: **New → Blueprint**.
2. Connect your GitHub and select `Anirudh-Saini10/ProctorVision`.
3. Render reads `render.yaml` from the repo root. You should see:
   - One web service: `proctorvision`
   - One persistent disk: `proctorvision-data` (1 GB)
4. Click **Apply**. First build takes **~8–12 minutes** (installing PyTorch, OpenCV, MediaPipe, npm packages).
5. When build is green, note your service URL — something like:
   ```
   https://proctorvision.onrender.com
   ```
6. Verify it's alive: open `https://proctorvision.onrender.com/api/health` — you should see `{"status":"healthy",...}`.

### Option B: Manual service configuration

1. In Render: **New → Web Service**.
2. Connect your GitHub and select `Anirudh-Saini10/ProctorVision`.
3. Configure:
   - **Name**: `proctorvision`
   - **Region**: Oregon (or nearest to you)
   - **Runtime**: Python
   - **Root Directory**: `.` (repo root, not `backend`)
   - **Build Command**: `cd frontend && npm install && npm run build && cd ../backend && pip install --no-cache-dir -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`
4. Under **Environment Variables**, add:
   - `JWT_SECRET`: (leave blank, Render will auto-generate)
   - `DATABASE_URL`: `sqlite:////var/data/proctorvision.db`
   - `TF_CPP_MIN_LOG_LEVEL`: `3`
   - `PYTHONUNBUFFERED`: `1`
5. Under **Disk**, add:
   - Name: `proctorvision-data`
   - Mount Path: `/var/data`
   - Size: 1 GB
6. Click **Deploy Web Service**. Wait for the build to finish.

---

## Verify End-to-End

1. Open your Render URL (e.g., `https://proctorvision.onrender.com`).
2. Click **Proctor sign-in** → **Create account** → register.
3. Create a new exam with 2-3 questions. Note the join code.
4. Open the same site in an **incognito window** (so it doesn't share auth).
5. Click **Join an exam** → enter the join code and a name.
6. Allow camera + microphone. The proctored session should start.
7. Back in your proctor tab → **Live console** — you should see the candidate listed.

---

## Updating the Deploy

Render auto-deploys on `git push` to `main`. Build time depends on what changed:

- Code-only changes: **~1–2 min** (pip packages cached)
- Dependency changes: **~8–12 min** (full rebuild)

No manual action needed after initial setup.

---

## Render Free Tier Notes

- The instance **sleeps after 15 min of inactivity** and takes ~30s to wake. First request after a long pause will be slow; subsequent ones are normal.
- If cold starts become annoying for demos, upgrade to **Starter ($7/mo)** for always-on. Set `plan: starter` in `render.yaml` and redeploy.

---

## Custom Domain (optional)

Render supports custom domains on free tier:

1. Go to your service → **Settings → Custom Domains**.
2. Add e.g., `proctorvision.com`.
3. Update your DNS records as instructed by Render.

No other configuration needed — same origin, no CORS.

---

## Troubleshooting

**"WARNING: Static frontend directory not found" in logs**
- The frontend build step failed. Check the build logs for npm errors.
- Common cause: `npm install` failed due to dependency conflicts or network issues.

**"404 Not Found" on the home page**
- Static file mount failed. Check that `frontend/dist` exists after the build.
- Verify the path in `backend/main.py` resolves correctly.

**WebSocket fails to connect**
- Confirm Render URL is `https://` (not `http://`). Frontend derives `wss://` from `https://`.
- Check that the `/ws` endpoint is registered before the static mount (it is in `main.py`).

**"401 Not authenticated" after login**
- JWT secret changed between deploys. Set `JWT_SECRET` explicitly in Render env (don't rely on `generateValue`) if you want tokens to survive redeploys reliably.

**"Could not allocate a unique exam code"**
- You hit a 1-in-billion collision. Try creating again. (Or there's a DB issue — check the SQLite file is writable on `/var/data`.)

**Render build fails on `ultralytics`**
- Free tier has 512 MB RAM build limit. If pip OOMs, switch to `plan: starter` for the build, then back to free for runtime.

**Slow first load**
- Render free tier cold start. Use [cron-job.org](https://cron-job.org) to ping `/api/health` every 10 min to keep it warm.
