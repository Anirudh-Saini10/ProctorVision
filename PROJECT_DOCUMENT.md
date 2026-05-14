# ProctorVision — Project Document & Interview Guide

> A comprehensive reference for understanding, explaining, and extending ProctorVision.

---

## Table of Contents

1. [Elevator Pitch](#1-elevator-pitch)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [System Architecture](#4-system-architecture)
5. [Feature Deep-Dives](#5-feature-deep-dives)
6. [Technology Choices & Justifications](#6-technology-choices--justifications)
7. [How to Explain Each Feature to an Interviewer](#7-how-to-explain-each-feature-to-an-interviewer)
8. [Challenges Faced & Solutions](#8-challenges-faced--solutions)
9. [Security & Privacy Considerations](#9-security--privacy-considerations)
10. [Performance & Scalability](#10-performance--scalability)
11. [Future Roadmap](#11-future-roadmap)
12. [Deployment Guide Summary](#12-deployment-guide-summary)
13. [Quick Q&A for Interviews](#13-quick-qa-for-interviews)

---

## 1. Elevator Pitch

**"ProctorVision is an AI-powered remote exam proctoring platform. Educators create exams with MCQs and short answers, share a 6-character join code with candidates, and watch them in real time through a live dashboard. The system uses computer vision — YOLOv8 for object detection, MediaPipe for face analysis — to detect phones, multiple faces, tab switching, and audio activity. Every violation generates an evidence snapshot. After the exam, the proctor gets a PDF integrity report and auto-graded MCQ scores."**

*If you have 30 seconds:* It's like Zoom + Turnitin + AI invigilation in one browser tab.

---

## 2. Problem Statement

### The Context
Remote exams exploded post-2020, but integrity remains broken:
- **Students** cheat with phones, second screens, or helpers off-camera
- **Institutions** pay $10–20 per candidate for proctoring tools that are invasive (full desktop surveillance, keystroke logging)
- **Proctors** stare at 30+ video feeds for hours — human attention degrades after 20 minutes
- **Reports** are just videos — nobody watches them

### What Existing Tools Get Wrong
| Tool Type | Problem |
|-----------|---------|
| **Record-and-review** | Hours of footage, nobody watches, cheating is only caught retroactively |
| **Always-on surveillance** | Records everything (privacy nightmare), requires software installation |
| **AI-only solutions** | High false positive rate — students penalised for blinking, thinking, or looking down |
| **Human-only solutions** | Doesn't scale. One proctor per 50 candidates = $$$ and fatigue |

### ProctorVision's Angle
**Browser-only, AI-augmented human proctoring.** No software to install. The AI handles the watching; the human proctor handles the decisions. Every AI flag comes with visual evidence, not just a number.

---

## 3. Solution Overview

### Two User Roles

**Proctor (educator):**
1. Register / log in
2. Create an exam with questions (MCQ or short answer)
3. System auto-generates a 6-character join code
4. Share the code with candidates
5. Open the **Live Console** to watch all active candidates
6. See real-time risk scores, violation counts, evidence snapshots
7. Force-end suspicious sessions manually
8. After exam: download PDF reports with integrity summary + auto-graded scores

**Candidate (student):**
1. Go to the site, click "Join exam"
2. Enter the join code and your name — no account needed
3. Allow camera and microphone
4. Complete a 5-point calibration (look at each corner + center)
5. Take the exam — MCQs are multiple-choice, short answers are free text
6. Submit when done

### What Happens Under the Hood
- Candidate's browser streams webcam frames to the backend via WebSocket (~5 FPS)
- Backend runs computer vision pipeline on each frame
- Violations are scored, risk is updated, evidence snapshots saved
- Proctor's dashboard receives the same stream via a relay WebSocket
- When the candidate submits, answers are auto-graded and an integrity report is generated

---

## 4. System Architecture

### High-Level Flow

```
Candidate Browser          Backend (Render)           Proctor Browser
       │                         │                           │
       │── webcam frames ───────►│                           │
       │     (WebSocket /ws)     │                           │
       │                         │── CV Pipeline ─────────────►│
       │                         │   (YOLOv8 + MediaPipe)    │
       │                         │                           │
       │                         │── risk + violations ─────►│
       │                         │   (WebSocket /ws/proctor)   │
       │                         │                           │
       │── quiz answers ─────────│                           │
       │                         │── auto-grade MCQs         │
       │                         │── generate PDF report     │
       │                         │                           │
```

### Backend Components

| File | Responsibility |
|------|---------------|
| `main.py` | FastAPI app, CORS, router wiring, startup events |
| `websocket_handler.py` | WebSocket lifecycle, session management, CV pipeline orchestration, proctor relay |
| `violation_logger.py` | Risk scoring algorithm, violation weights, session summary generation |
| `report_generator.py` | PDF report builder (ReportLab) with charts and evidence |
| `db.py` | SQLModel engine, SQLite file, session dependency |
| `models.py` | Schema: Proctor, Exam, Question, Attempt, Answer |
| `security.py` | JWT creation/verification, bcrypt password hashing, exam code generation |
| `routes/auth.py` | `/api/auth/register`, `/api/auth/login`, `/api/auth/me` |
| `routes/exams.py` | CRUD for exams, public lookup by code, attempt listing |
| `routes/attempts.py` | Start attempt, submit answers + auto-grade, fetch result |

### Database Schema

```
Proctor (1) ────< Exam (n) ────< Question (n)
                      │
                      └──< Attempt (n) ────< Answer (n)
```

- **Proctor**: email, name, password_hash
- **Exam**: title, description, code (unique), strictness, duration, status (draft/live/closed)
- **Question**: prompt, kind (mcq/short), options (JSON), correct_index, points, display order
- **Attempt**: candidate_name, started_at, submitted_at, status, auto_score, integrity_summary (JSON)
- **Answer**: selected_index or text, is_correct flag

### Frontend Components

| Page | Purpose |
|------|---------|
| `Landing.jsx` | Marketing page with links to join or proctor login |
| `Join.jsx` | Candidate enters join code + name, fetches exam, starts attempt |
| `Calibrate.jsx` | 5-point face calibration before exam |
| `Exam.jsx` | Quiz runner with timer, MCQ/short-answer rendering, submission |
| `ProctorLogin.jsx` | Combined login/register for proctors |
| `ProctorExams.jsx` | Dashboard listing all exams with join codes and attempt counts |
| `ProctorExamEditor.jsx` | Full exam authoring — add/edit questions, set duration |
| `ProctorMonitor.jsx` | **Live console** — candidate cards with video, risk meter, evidence gallery |
| `Report.jsx` | Post-session report viewer |

---

## 5. Feature Deep-Dives

### 5.1 Real-Time Computer Vision Pipeline

**What it is:** A frame-by-frame analysis of the candidate's webcam feed running on the backend.

**How it works:**
1. Candidate's browser captures a webcam frame and sends it as base64 JPEG over WebSocket
2. Backend decodes the frame and runs three parallel analyses:
   - **YOLOv8n** (6MB model): Detects phones, laptops, books, people
   - **MediaPipe Face Mesh**: Counts faces, estimates gaze direction, checks if eyes are closed
   - **Browser events**: Tab visibility API detects tab switching; Web Audio API detects speech
3. Each detector returns a confidence score and bounding box
4. `violation_logger.py` weights the detections:
   - Phone detected: +20 risk points
   - Multiple faces: +15 risk points
   - Face not visible: +8 risk points
   - Tab switched: +5 risk points
   - Audio activity: +5 risk points
   - Proctor manual flag: +25 risk points
5. Risk decays naturally by 1 point per second when no violations are active
6. The pipeline sends back: current risk score, active violations, calibration progress

**Why these weights:** Phones are the #1 cheating vector in remote exams. Multiple faces = clear proxy/helper situation. Face absence = looking down/away. Tab switching = searching answers. The proctor flag is highest because it's a human override.

**Evidence snapshots:** Every time a violation is logged, the current frame is saved as a JPEG thumbnail. The proctor can click to enlarge. This is critical — it transforms the system from "trust the AI number" to "see what the AI saw."

### 5.2 Ghost Session Fix

**The bug:** React 18 StrictMode mounts components twice in development. The `Calibrate.jsx` page sent two `session_start` messages on the same WebSocket. The backend created two sessions for one candidate. The first session became a "ghost" — still listed in the proctor dashboard but with no active connection.

**The fix:**
- The backend now tracks the last session created per WebSocket connection
- If a duplicate `session_start` arrives on the same socket, the previous session is archived with status `superseded`
- `list_active_sessions()` filters out `superseded` sessions
- Result: dashboard only shows real, active sessions

### 5.3 Auto-Grading

**How it works:**
- On submission, the backend fetches all questions for that exam
- For each MCQ: compare `selected_index` to `correct_index`
- Correct: add `points` to `auto_score`
- Short answers: stored as text, contribute 0 to auto_score (manual review by proctor)
- `max_auto_score` = sum of points for all MCQs
- Results stored on the Attempt row for the PDF report

**Edge case:** Re-submitting an already-submitted attempt is idempotent — returns the existing score without re-grading.

### 5.4 PDF Report Generation

**What goes in:**
- Candidate name, exam title, date
- Integrity score (0–100, inverse of peak risk)
- Peak risk level and when it occurred
- Violation breakdown table (type, count, timestamps)
- Auto-graded score (X / Y)
- Evidence snapshot grid
- Summary text: "This session showed moderate risk with 3 phone detections..."

**Tech:** ReportLab with custom styles, A4 page size, embedded JPEG thumbnails.

### 5.5 Exam Code System

**How codes work:**
- 6-character alphanumeric using `ABCDEFGHJKMNPQRSTUVWXYZ23456789`
- Excludes ambiguous characters: 0/O, 1/I/L
- Codes are unique across all exams (DB unique constraint)
- Code is generated on exam creation, not changeable
- Candidates enter codes case-insensitively; backend converts to uppercase

**Why this matters:** In a video call, "A3K7QF" is unambiguous. "a3k7qf" or "A3K70F" would cause confusion.

---

## 6. Technology Choices & Justifications

### Why YOLOv8 (not YOLOv5 or Detectron2)?
- **YOLOv8n** is 6MB and runs at ~30 FPS on CPU
- Single-shot detector = fast enough for real-time proctoring
- Pre-trained COCO weights detect phone, person, laptop, book out of the box
- Ultralytics API is one line: `model(frame)`

### Why MediaPipe (not dlib or OpenCV Haar)?
- Face mesh gives 468 landmarks = precise eye/head orientation
- Runs on CPU at ~15 FPS
- No model download at runtime (bundled in the pip package)
- Google's production-grade accuracy

### Why SQLite (not PostgreSQL or MongoDB)?
- Zero configuration — file-based, no daemon
- SQLModel gives us Pydantic + SQLAlchemy in one
- At portfolio scale (<10k attempts), SQLite is faster than a networked DB
- Render's persistent disk keeps the file across deploys
- Can migrate to PostgreSQL later by changing one connection string

### Why FastAPI (not Flask or Django)?
- Native WebSocket support with `async/await`
- Auto-generated OpenAPI docs at `/docs`
- Pydantic request/response validation
- Built for high-concurrency async I/O (candidate streams + proctor dashboards)

### Why React + Vite (not Next.js)?
- SPA is correct for this app — no SSR needed
- Vite HMR is instant
- WebSocket connections are client-side only
- Vercel static hosting is free and global CDN

### Why JWT (not session cookies)?
- Stateless — no session store needed
- Works across origins (Vercel frontend → Render backend)
- No CSRF vulnerability since we don't use cookies
- 12-hour expiry = proctor stays logged in for a full exam day

---

## 7. How to Explain Each Feature to an Interviewer

### "Tell me about the CV pipeline."
> "The candidate's browser sends webcam frames over WebSocket to our FastAPI backend. On each frame we run YOLOv8n for object detection — phones, books, extra people — and MediaPipe Face Mesh for face count and gaze estimation. Each detector contributes to a risk score: phone = +20, multiple faces = +15, face not visible = +8. Risk decays when behaviour normalises. The proctor sees a live risk meter and evidence snapshots for every violation."

### "How do you handle false positives?"
> "Two layers. First, the AI only flags when confidence is above a threshold. Second, the proctor has a manual override — they can flag or unflag any candidate. Third, every violation comes with a snapshot so the proctor can verify. In the future, we're adding an AI agent that warns the candidate before logging a violation, giving them a chance to self-correct."

### "Why WebSocket and not HTTP polling?"
> "We need ~5 FPS frame streaming. HTTP polling would mean 5 requests per second per candidate — unacceptable overhead. WebSocket gives us a persistent duplex connection: candidate sends frames up, backend sends risk updates down, all on one TCP connection."

### "How does the proctor see multiple candidates?"
> "When a proctor opens the Live Console, their browser connects to `/ws/proctor`. The backend maintains a fan-out: every candidate frame and every risk update is broadcast to all connected proctor sockets. It's a pub-sub pattern — one publisher (candidate), multiple subscribers (proctors)."

### "What about privacy?"
> "Frames are processed server-side and discarded after the session. Evidence snapshots are JPEG thumbnails, not full video. No screen recording, no keystroke logging. The candidate explicitly allows camera access and can revoke it at any time. We're exploring local inference as a future option — frames never leave the candidate's machine."

### "How does auto-grading work?"
> "When a candidate submits, the backend fetches the exam's questions. For each MCQ, we compare the candidate's selected index to the stored correct index. Correct answers add the question's point value to the auto-score. Short answers are stored as free text for manual review. The result is persisted to the Attempt row and included in the PDF report."

---

## 8. Challenges Faced & Solutions

### Challenge 1: React StrictMode double-mount creating ghost sessions
- **Symptom:** Proctor dashboard showed duplicate sessions for one candidate
- **Root cause:** React 18 mounts components twice in dev to test cleanup. `Calibrate.jsx` sent `session_start` twice.
- **Fix:** Backend tracks the last session per WebSocket. Duplicate starts archive the previous session as `superseded`. Dashboard filters them out.

### Challenge 2: CORS between Vercel frontend and Render backend
- **Symptom:** Browser blocked API calls with "No Access-Control-Allow-Origin header"
- **Root cause:** Render didn't know the Vercel origin
- **Fix:** Since auth is JWT header-based (not cookies), we allow all origins with `allow_origins=["*"]` and `allow_credentials=False`. This is safe for JWT and removes deployment friction.

### Challenge 3: PyTorch/ultralytics build taking 30 minutes on Render
- **Symptom:** First deploy was unbearably slow
- **Fix:** Pre-commit `yolov8n.pt` to the repo so it's already present at build time. Use `--no-cache-dir` in pip to avoid cache bloat.

### Challenge 4: Phone detection not sensitive enough
- **Symptom:** Candidates holding phones below the frame weren't caught
- **Fix:** Increased phone violation weight from 10 to 20 risk points. Added evidence snapshots so proctors can review ambiguous detections.

### Challenge 5: SQLite `check_same_thread` error
- **Symptom:** `SQLite objects created in a thread can only be used in that same thread`
- **Fix:** Added `connect_args={"check_same_thread": False}` in `create_engine()`. FastAPI runs request handlers in a threadpool; each request gets its own session via the `get_session` dependency.

---

## 9. Security & Privacy Considerations

| Concern | Mitigation |
|---------|-----------|
| **Stolen JWT** | 12-hour expiry; no refresh tokens (portfolio simplicity) |
| **Password storage** | bcrypt with auto-salt |
| **SQL injection** | SQLModel/SQLAlchemy ORM — no raw SQL |
| **Frame interception** | Frames travel over WSS (encrypted). No persistent video storage. |
| **Candidate identity** | No accounts, no PII beyond a name. Attempt ID is the only identifier. |
| **Proctor access** | JWT-gated routes. Proctors can only see their own exams and attempts. |
| **Exam code guessing** | 6 chars from 32-symbol alphabet = 1 billion combinations. Rate limiting via unique constraint. |

---

## 10. Performance & Scalability

### Current Limits (Free Tier)
- **Render:** 512 MB RAM, 1 vCPU
- **Frame processing:** ~5 FPS per candidate at 320x240 resolution
- **Concurrent candidates:** Estimated 5–10 before CPU saturation
- **Concurrent proctors:** Unlimited (read-only relay)

### Scaling Path
1. **Vertical:** Render Starter plan ($7/mo) → 2 vCPU, 1 GB RAM → ~20 candidates
2. **Horizontal:** Run multiple Render instances behind a load balancer with sticky WebSocket sessions
3. **GPU:** Render GPU instances or RunPod for YOLOv8 → 100+ FPS, 50+ candidates
4. **DB:** SQLite → PostgreSQL on Render ($0 addon) for 100k+ attempts

### Optimisations Already Applied
- Frames downscaled to 320x240 before CV processing
- JPEG quality set to 60% for WebSocket transport
- YOLOv8n (nano) model — smallest in the family
- Risk score batching: updates sent every 2 seconds, not per-frame
- SQLite `PRAGMA journal_mode=WAL` (implicit via SQLModel) for concurrent reads

---

## 11. Future Roadmap

### Phase 1: AI Proctor Agent (High Priority)
Replace silent rule-based detection with a multimodal AI agent that:
- Observes the candidate via VLM (Gemini 2.0 Flash / GPT-4o-mini)
- Reasons about behaviour: "looking down for 8s, consistent with phone in lap"
- Warns the candidate via browser TTS: "Please keep your eyes on the screen"
- Re-observes — if corrected, no violation logged
- If ignored after 2 warnings, escalates to logged violation with reasoning trace

**Why this matters:** Eliminates false positives. Students get a chance to self-correct. Every flag is explainable. Scales to new cheating patterns without hand-tuned heuristics.

**Rollout plan:** Shadow mode → silent warnings → escalation authority → voice channel

### Phase 2: Eye-Tracking Calibration
- Per-candidate gaze heatmap during calibration
- Detect "looking at second monitor" (gaze drifts off-screen horizontally)
- More accurate than head-pose estimation

### Phase 3: Screen Recording (Optional)
- For coding/software exams: optional screen share
- Proctor sees candidate's IDE in a picture-in-picture panel
- Tab switch detection becomes screen-level, not just browser-level

### Phase 4: Two-Way Chat
- Proctor can send messages to candidates during the exam
- "Please show your desk" — candidate replies with a webcam reposition
- All messages logged in the report

### Phase 5: Plagiarism Detection
- TF-IDF similarity across all submissions for the same exam
- Flag candidates with unusually similar short answers
- Proctor review dashboard for suspected collusion

### Phase 6: Mobile App
- Native iOS/Android proctor console
- Push notifications when a candidate's risk spikes
- Review evidence snapshots on mobile

---

## 12. Deployment Guide Summary

**Hybrid: Render (backend) + Vercel (frontend)**

| Step | Action | Time |
|------|--------|------|
| 1 | Push code to GitHub | 1 min |
| 2 | Render: New → Blueprint → connect repo | 2 min |
| 3 | Wait for first build | ~10 min |
| 4 | Note Render URL | instant |
| 5 | Vercel: New Project → import repo | 2 min |
| 6 | Set `VITE_API_URL` to Render URL | 1 min |
| 7 | Deploy frontend | ~2 min |
| 8 | Test end-to-end | 5 min |

**Total first-time setup: ~20 minutes**

See `DEPLOY.md` for the full guide with screenshots and troubleshooting.

---

## 13. Quick Q&A for Interviews

**Q: How many candidates can one proctor monitor?**
A: The dashboard scales to 20+ candidates per screen with grid view. The AI handles all frame processing, so the proctor only intervenes on flagged candidates.

**Q: What happens if the candidate loses internet?**
A: WebSocket disconnects. The session is marked `abandoned`. The candidate can re-join with the same code — a new attempt is created, but the proctor sees the disconnection in the dashboard.

**Q: Can candidates cheat by covering the camera?**
A: Face absence is a violation (+8 risk). If the camera is covered for >10 seconds, the risk score climbs. The proctor is notified.

**Q: Why not use a commercial proctoring service?**
A: Commercial services cost $10–20 per exam and require invasive software installation. ProctorVision is free at portfolio scale, browser-only, and the educator owns the data.

**Q: How do you prevent someone from joining with a fake name?**
A: For portfolio scale, we trust the candidate. In production, institutions would cross-reference the name with their student roster. The proctor sees the entered name in the dashboard and can verify identity visually.

**Q: What's the most impressive technical part?**
A: The real-time fan-out architecture. One candidate's webcam stream is processed by AI, then simultaneously broadcast to multiple proctor dashboards with evidence snapshots — all on WebSockets, no polling, no video storage.

---

*Last updated: May 2026*
*Built by Anirudh Saini — [GitHub](https://github.com/Anirudh-Saini10)*
