# Deploying ProctorVision

Hybrid setup: **Vercel** for the frontend (Vite static build), **Render** for the backend (FastAPI + WebSocket + SQLite + YOLOv8).

Both have generous free tiers. Total monthly cost at portfolio scale: **$0**.

---

## Prerequisites

1. The code is on GitHub. Your repo: `Anirudh-Saini10/ProctorVision`.
2. Commit `backend/yolov8n.pt` to the repo (it's ~6 MB) so the model is available at boot. If `.gitignore` excludes it, remove that line and `git add backend/yolov8n.pt`.
3. Free accounts on:
   - [render.com](https://render.com) (GitHub sign-in)
   - [vercel.com](https://vercel.com) (GitHub sign-in)

---

## Step 1 — Deploy the backend on Render

1. In Render: **New → Blueprint**.
2. Connect your GitHub and select `Anirudh-Saini10/ProctorVision`.
3. Render reads `render.yaml` from the repo root. You should see:
   - One web service: `proctorvision-api`
   - One persistent disk: `proctorvision-data` (1 GB)
4. It will ask you to fill in the `FRONTEND_ORIGINS` env var. **Leave it blank for now** — we'll set it after the frontend is deployed.
5. Click **Apply**. First build takes **~8–12 minutes** (installing PyTorch, OpenCV, MediaPipe, etc.).
6. When build is green, note your service URL — something like:
   ```
   https://proctorvision-api.onrender.com
   ```
7. Verify it's alive: open `https://proctorvision-api.onrender.com/api/health` — you should see `{"status":"healthy",...}`.

### Render free tier notes

- The instance **sleeps after 15 min of inactivity** and takes ~30s to wake. First request after a long pause will be slow; subsequent ones are normal.
- If this becomes annoying for demos, upgrade to **Starter ($7/mo)** for always-on. Set `plan: starter` in `render.yaml` and redeploy.

---

## Step 2 — Deploy the frontend on Vercel

1. In Vercel: **Add New → Project → Import Git Repository** → select `Anirudh-Saini10/ProctorVision`.
2. Configure:
   - **Framework**: Vite (auto-detected)
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` (default)
   - **Output Directory**: `dist` (default)
3. Under **Environment Variables**, add:
   - Key: `VITE_API_URL`
   - Value: your Render URL from Step 1, e.g. `https://proctorvision-api.onrender.com`
4. Click **Deploy**. Build takes ~2 minutes.
5. When done, Vercel gives you a URL like:
   ```
   https://proctorvision.vercel.app
   ```

---

## Step 3 — Wire CORS

Go back to Render → your service → **Environment** tab.

Set `FRONTEND_ORIGINS` to your Vercel URL **(no trailing slash)**:

```
https://proctorvision.vercel.app
```

If you want to also allow preview deployments, comma-separate:

```
https://proctorvision.vercel.app,https://proctorvision-git-main-yourname.vercel.app
```

Save → Render automatically redeploys (~30s).

---

## Step 4 — Verify end-to-end

1. Open `https://proctorvision.vercel.app`.
2. Click **Proctor sign-in** → **Create account** → register.
3. Create a new exam with 2-3 questions. Note the join code.
4. Open the same site in an **incognito window** (so it doesn't share auth).
5. Click **Join an exam** → enter the join code and a name.
6. Allow camera + microphone. The proctored session should start.
7. Back in your proctor tab → **Live console** — you should see the candidate listed.

---

## Updating the deploy

Both platforms auto-deploy on `git push` to `main`:

- Frontend updates → Vercel rebuilds (~1-2 min).
- Backend updates → Render rebuilds (~3-8 min if dependencies changed, ~1-2 min for code-only).

No manual action needed after initial setup.

---

## Custom domain (optional)

Both Vercel and Render support custom domains on free tier:

- **Vercel**: Project → Settings → Domains → add e.g. `proctorvision.com`.
- **Render**: Service → Settings → Custom Domains.

Update `VITE_API_URL` and `FRONTEND_ORIGINS` if you change either URL.

---

## Troubleshooting

**WebSocket fails to connect**
- Confirm Render URL is `https://` (not `http://`). Frontend derives `wss://` from `https://`.
- Check `FRONTEND_ORIGINS` matches the Vercel URL exactly, no trailing slash.

**"401 Not authenticated" after login**
- JWT secret changed between deploys. Set `JWT_SECRET` explicitly in Render env (don't rely on `generateValue`) if you want tokens to survive redeploys reliably.

**"Could not allocate a unique exam code"**
- You hit a 1-in-billion collision. Try creating again. (Or there's a DB issue — check the SQLite file is writable on `/var/data`.)

**Render build fails on `ultralytics`**
- Free tier has 512 MB RAM build limit. If pip OOMs, switch to `plan: starter` for the build, then back to free for runtime.

**Slow first load**
- Render free tier cold start. Use [cron-job.org](https://cron-job.org) to ping `/api/health` every 10 min to keep it warm.
