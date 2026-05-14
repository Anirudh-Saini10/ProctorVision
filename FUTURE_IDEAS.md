# ProctorVision — Future Ideas & Roadmap

A living document for ideas that came up during development but are out of
scope for the current iteration. Each entry should describe the **problem**
it solves, a sketch of **how it would work**, and the **trade-offs**.

---

## 1. Interactive AI Proctor Agent (high-priority, post-MVP)

### Problem it solves
The current rule-based detectors are forced into a binary choice on
ambiguous behaviours:

- A student looking down might be **reading a phone on their lap** or
  might just be **thinking / blinking / glancing at their hands**.
- A student looking off to the side might be **peeking at a second
  screen** or might just be **resting their eyes**.
- A student speaking might be **collaborating with someone** or might
  just be **muttering / reading the question aloud to themselves**.

In every one of these cases the system today either:
- silently lets it pass (false negative — real cheating slips through), or
- flags it (false positive — honest students penalised).

There is **no explainability** and **no chance for the student to correct
their behaviour** before being flagged. That is unfair, and it is the
single biggest weakness of pure heuristic-based proctoring.

### The idea
Replace (or augment) the silent rule-based pipeline with a real-time
**multimodal AI agent** that watches the candidate, reasons about what
it sees, and can **speak to the candidate** before deciding to flag.

The agent's loop, conceptually:

1. **Observe** — receives the live webcam stream + audio + screen state.
2. **Reason** — a small VLM (vision-language model) running locally or
   on the proctor server forms a hypothesis: *"the candidate has been
   looking down and to the right for 8 seconds, this is consistent with
   reading a phone in their lap."*
3. **Intervene** — instead of silently logging a violation, the agent
   *speaks*: a TTS warning is delivered through the candidate's
   speakers / a chat bubble appears: *"Please keep your eyes on the
   screen. Do not look down for extended periods."*
4. **Re-observe** — does the candidate correct their behaviour within
   the next ~10 seconds?
   - **Yes** → no violation logged. The agent silently records the
     incident as a *warning resolved*.
   - **No** → the agent escalates: a stronger warning, then a logged
     violation with full context: *"Candidate continued to look down
     after 2 verbal warnings."* This is now **explainable** evidence
     instead of a raw threshold trip.

### Why this is much better than today
- **Explainability for free.** Every flagged violation comes with the
  agent's reasoning trace and the warnings it issued. A reviewer can
  see exactly *why* the system concluded cheating, not just a numeric
  threshold trip.
- **Fairness.** Students get a chance to correct themselves — a person
  who genuinely wasn't cheating will simply look up when asked, and no
  flag is logged. Today's system has no such safety valve.
- **Catches behaviours we can't catch today.** "Looking down" is
  intentionally not flagged in the current build because it's too
  ambiguous. With an agent, ambiguity becomes an opportunity to ask
  rather than a reason to give up.
- **Scales to new cheating patterns** without us writing new heuristics.
  The agent generalises: a smart-watch peek, a reflection in a window,
  someone whispering off-camera — none of these need a hand-tuned
  detector.

### Sketch of architecture
- **Realtime VLM** — Gemini 2.0 Flash, GPT-4o-mini, or a local
  Llama-3.2-Vision running on the proctor server. Sample frames at
  ~1 Hz; full reasoning pass every ~3 seconds.
- **Agent state machine** with explicit phases:
  `OBSERVING → SUSPICION → WARNING_1 → WARNING_2 → FLAG`.
  Transitions logged for the report.
- **TTS channel** — browser-side `SpeechSynthesis` for warnings (low
  latency, no extra round-trip).
- **Live transcript pane** in the proctor dashboard so the human proctor
  can see what the agent is saying to each candidate.
- **Privacy guardrails** — the agent's view of the frame never leaves
  the institution's infrastructure unless the student opts in. Frames
  are downsampled and audio is transcribed before any cross-network hop.

### Trade-offs / risks
- **Cost.** A VLM call every 3s × N candidates × 1h exam isn't free.
  Could be mitigated with a small "is anything interesting happening?"
  router model that only invokes the heavy VLM when the rule-based
  layer flags suspicion.
- **Latency.** A 2-3s reasoning loop is fine for *behaviour over time*
  but useless for *instant* events (someone yanks out a phone for 1s).
  Keep the existing detectors as a fast first layer; the agent
  arbitrates the ambiguous cases only.
- **Adversarial students.** Once they know an agent is watching, they
  may try to game it (closed eyes, pretend to read screen). The agent
  will need to be trained on these patterns, just like the heuristics.
- **TTS interruption.** Speaking *to* the candidate during an exam is a
  real UX disruption. Could be opt-in: warnings appear as silent toasts
  by default, with TTS only after the second silent warning is ignored.
- **Hallucinations.** A VLM that confidently says "you are reading from
  a notebook" when the candidate is just thinking is worse than no
  agent at all. Mitigation: only let the agent *escalate* an existing
  detector signal — never *originate* a violation alone.

### Suggested incremental rollout
1. **Phase 1** — Agent runs in *shadow mode*. It receives the same
   stream and writes its reasoning to the report, but does NOT speak to
   the candidate. We collect data on agreement vs. the heuristic layer.
2. **Phase 2** — Agent gets a silent "warning" channel: a small toast
   in the candidate's UI saying *"Please keep your eyes on the screen."*
   Still doesn't log violations on its own.
3. **Phase 3** — Agent gets escalation authority: after 2 ignored
   silent warnings on the same behaviour, it can promote a heuristic
   signal into a logged violation with its reasoning attached.
4. **Phase 4** — Voice channel and live transcript for the human
   proctor.

---

## (template — add new ideas below)

## N. Title

### Problem it solves
…

### The idea
…

### Trade-offs / risks
…
