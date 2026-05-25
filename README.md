

# ProctorVision

> AI-powered remote exam proctoring with real-time computer vision, live risk scoring, and full exam authoring — built for educators who need integrity without invigilation halls.

**Live Demo:** -https://anirudhsaini-proctorvision.hf.space/

---

## What It Does

ProctorVision is a full-stack remote proctoring platform that lets educators create exams, share join codes with candidates, and monitor them in real time via AI-driven behavioural analysis.

**For Proctors:**
- Create exams with MCQ and short-answer questions
- Auto-generate unique 6-character join codes
- Watch a live console of all active candidates
- See a real-time risk meter per candidate (0–100)
- Review evidence snapshots for every violation
- Download PDF integrity reports post-exam
- Auto-grade MCQs instantly

**For Candidates:**
- Join any exam with a code + name — no account needed
- Browser-based camera calibration (no install)
- Real-time feedback on posture and environment
- Full quiz experience with timer and navigation

**The AI Pipeline watches for:**
- **Phone / object detection** (YOLOv8)
- **Face presence & gaze** (MediaPipe)
- **Multiple faces** (proxy / helper detection)
- **Tab switching** (browser focus loss)
- **Audio activity** (unexpected speech)
- **Manual proctor flags** (human override)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, Tailwind CSS, Framer Motion, WebSocket |
| **Backend** | FastAPI, Python 3.11 |
| **CV / ML** | YOLOv8 (Ultralytics), MediaPipe Face Mesh, OpenCV |
| **Real-time** | Native WebSocket (candidate → server → proctor relay) |
| **Auth** | JWT (bcrypt + python-jose) |
| **Database** | SQLModel + SQLite (zero-ops, file-based) |
| **Reports** | ReportLab (PDF generation) |
| **Deploy** | HuggingFace Spaces (single service, frontend + backend) |

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Candidate     │      │   ProctorVision  │      │    Proctor      │
│   Browser       │◄────►│   Backend        │◄────►│   Dashboard     │
│                 │  WS  │   (HFSpaces)     │  WS  │                 │
│  Webcam stream  │      │                  │      │  Live console   │
│  Quiz UI        │      │  CV Pipeline     │      │  Risk meters    │
└─────────────────┘      │  YOLOv8 + MP     │      │  Snapshots      │
                         │  SQLite DB       │      └─────────────────┘
                         └──────────────────┘
                                  │
                          ┌───────┴───────┐
                          │   PDF Reports │
                          │   SQLite      │
                          └───────────────┘
```

---

## Quick Start (Local)

### 1. Clone & setup

```bash
git clone https://github.com/Anirudh-Saini10/ProctorVision.git
cd ProctorVision
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### 4. Test the flow

1. **Proctor** → `/proctor/login` → Create account
2. **New exam** → Add 2 MCQs → Copy join code
3. **Candidate** (incognito) → `/join` → Enter code + name
4. **Allow camera** → Proctoring starts
5. **Proctor tab** → **Live console** → Watch the candidate

---

## Deploy (Production)

See [`DEPLOY.md`](DEPLOY.md) for the full step-by-step guide.

**Summary:**
- Frontend built into backend, served by FastAPI
- Same origin = no CORS, zero config
- Cost at portfolio scale: **$0**

---

## Key Features Deep-Dive

### Real-Time CV Pipeline
- Receives webcam frames at ~5 FPS via WebSocket
- Runs YOLOv8n for phone/object detection
- MediaPipe Face Mesh for face count, gaze, and presence
- Violations weighted by severity (phone = 20pts, face absence = 8pts)
- Risk score decays naturally when behaviour normalises

### Evidence Snapshots
Every violation triggers a frame capture. Proctors see a gallery of thumbnail evidence per candidate, clickable for full-size review. No more "trust the number" — see exactly what the AI saw.

### Ghost Session Fix
React 18 StrictMode double-mounts can send duplicate `session_start`. The backend detects this, archives the superseded session, and keeps the dashboard clean.

### Auto-Grading
MCQs are graded instantly on submission. Short answers are stored for manual review. Both contribute to a unified score + integrity report.

---

## Project Structure

```
ProctorVision/
├── backend/
│   ├── main.py                 # FastAPI entry point + static file serving
│   ├── websocket_handler.py    # WS + CV pipeline orchestration
│   ├── violation_logger.py     # Risk scoring & session summary
│   ├── report_generator.py     # PDF report builder
│   ├── db.py, models.py        # SQLModel schema
│   ├── security.py             # JWT + bcrypt
│   ├── yolov8n.pt              # YOLOv8 model weights
│   └── routes/
│       ├── auth.py             # Proctor register / login
│       ├── exams.py            # Exam CRUD + public lookup
│       └── attempts.py         # Candidate attempt lifecycle
├── frontend/
│   ├── src/
│   │   ├── pages/              # Join, Exam, Calibrate,
│   │   │                         ProctorLogin, ProctorExams,
│   │   │                         ProctorExamEditor, ProctorMonitor
│   │   ├── components/         # Reusable UI
│   │   ├── hooks/              # useProctorSocket, useAudioActivity
│   │   ├── lib/api.js          # REST client
│   │   └── state/              # AuthContext, SessionContext
├── render.yaml                 # Render blueprint (builds frontend + backend)
├── DEPLOY.md                   # Deployment guide
└── FUTURE_IDEAS.md             # Roadmap & research
```

---

## Future Roadmap

See [`FUTURE_IDEAS.md`](FUTURE_IDEAS.md) for the full research doc. Top items:

- **Interactive AI Proctor Agent** — multimodal VLM that observes, reasons, warns candidates, and only escalates after self-correction chances. Eliminates false positives.
- **Eye-tracking calibration** — per-candidate gaze mapping for precise "looking away" detection
- **Screen recording** — optional tab-level capture for software engineering exams
- **Live two-way chat** — proctor ↔ candidate messaging during the session
- **Plagiarism detection** — similarity scoring across submissions for the same exam
- **Mobile app** — native iOS/Android proctor console for educators on the move

---

## License

MIT — see [LICENSE](LICENSE)

---

Built by [Anirudh Saini](https://github.com/Anirudh-Saini10)

SOME DEMO PICTURES!
<img width="758" height="471" alt="Screenshot 2026-05-25 120758" src="https://github.com/user-attachments/assets/0a49739f-9c16-4cd4-b8ba-d3a5e871b1ba" />
<img width="843" height="472" alt="Screenshot 2026-05-25 122219" src="https://github.com/user-attachments/assets/a52b54b6-ea57-4bd8-a997-84c060e34fc0" />
<img width="1345" height="613" alt="Screenshot 2026-05-25 131650" src="https://github.com/user-attachments/assets/69c8dd7b-d996-49ac-8322-7b3d6ee6921b" />
<img width="1334" height="616" alt="Screenshot 2026-05-25 131734" src="https://github.com/user-attachments/assets/3f2ebb7b-150e-48e5-9bcf-75842d3f71da" />
<img width="1346" height="621" alt="Screenshot 2026-05-25 132146" src="https://github.com/user-attachments/assets/b0e72bf3-0717-4502-aa22-3af30cfb9591" />
<img width="1341" height="620" alt="Screenshot 2026-05-25 132452" src="https://github.com/user-attachments/assets/ecc02db3-d103-4a60-b2c6-36866a1e4ea1" />
<img width="1335" height="612" alt="Screenshot 2026-05-25 133050" src="https://github.com/user-attachments/assets/db40cc05-87b7-4792-9dac-7429ed844eaf" />
<img width="1349" height="618" alt="Screenshot 2026-05-25 133212" src="https://github.com/user-attachments/assets/f9697968-c50f-4322-9bdd-33d0edd1a519" />
<img width="1356" height="615" alt="Screenshot 2026-05-25 134016" src="https://github.com/user-attachments/assets/f25af0ac-b271-4766-a325-b965b75f5583" />
<img width="1354" height="631" alt="Screenshot 2026-05-25 134100" src="https://github.com/user-attachments/assets/dbea3a01-951f-40e0-bf2d-a6f167ff1db8" />










