import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Plus, Trash2, Save, Copy, Check, FileText } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import { examsApi } from '../lib/api.js'

/**
 * Create-or-edit page for a single exam. We use one component for
 * both because the UI is identical — only the network round-trips at
 * save time differ.
 *
 * Validation matches the backend (mcq needs ≥2 options + valid
 * correct_index; short forbids options/correct_index). We surface
 * server errors verbatim if validation slips past us locally.
 */
export default function ProctorExamEditor() {
  const { id } = useParams()
  const isNew = !id || id === 'new'
  const navigate = useNavigate()

  const [exam, setExam] = useState(() => ({
    title: '',
    description: '',
    strictness: 'moderate',
    duration_min: 30,
    status: 'live',
  }))
  const [questions, setQuestions] = useState([])
  const [attempts, setAttempts] = useState([])
  const [code, setCode] = useState(null)
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // Hydrate when editing.
  useEffect(() => {
    if (isNew) {
      setQuestions([blankQuestion(0)])
      return
    }
    examsApi
      .get(id)
      .then((e) => {
        setExam({
          title: e.title,
          description: e.description,
          strictness: e.strictness,
          duration_min: e.duration_min,
          status: e.status,
        })
        setQuestions(
          (e.questions || []).map((q) => ({
            ...q,
            options: q.options ?? ['', '', '', ''],
            correct_index: q.correct_index ?? 0,
          }))
        )
        setCode(e.code)
      })
      .catch((err) => setError(err.message))

    examsApi.attempts(id).then(setAttempts).catch(() => {})
  }, [id, isNew])

  const addQuestion = () =>
    setQuestions((prev) => [...prev, blankQuestion(prev.length)])

  const removeQuestion = (i) =>
    setQuestions((prev) => prev.filter((_, idx) => idx !== i))

  const updateQuestion = (i, patch) =>
    setQuestions((prev) =>
      prev.map((q, idx) => (idx === i ? { ...q, ...patch } : q))
    )

  const validate = () => {
    if (!exam.title.trim()) return 'Title is required.'
    if (questions.length < 1) return 'At least one question is required.'
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i]
      if (!q.prompt.trim()) return `Question ${i + 1}: prompt required.`
      if (q.kind === 'mcq') {
        const opts = (q.options || []).map((o) => (o || '').trim()).filter(Boolean)
        if (opts.length < 2) return `Question ${i + 1}: MCQ needs ≥ 2 options.`
        if (
          q.correct_index === null ||
          q.correct_index === undefined ||
          q.correct_index < 0 ||
          q.correct_index >= opts.length
        )
          return `Question ${i + 1}: pick a correct option.`
      }
    }
    return null
  }

  const onSave = async () => {
    const v = validate()
    if (v) {
      setError(v)
      return
    }
    setError('')
    setBusy(true)
    try {
      const payloadQs = questions.map((q) =>
        q.kind === 'mcq'
          ? {
              kind: 'mcq',
              prompt: q.prompt.trim(),
              options: (q.options || []).map((o) => (o || '').trim()).filter(Boolean),
              correct_index: q.correct_index ?? 0,
              points: q.points || 1,
            }
          : {
              kind: 'short',
              prompt: q.prompt.trim(),
              options: null,
              correct_index: null,
              points: q.points || 1,
            }
      )
      if (isNew) {
        const created = await examsApi.create({
          title: exam.title.trim(),
          description: exam.description.trim(),
          strictness: exam.strictness,
          duration_min: exam.duration_min,
          questions: payloadQs,
        })
        navigate(`/proctor/exams/${created.id}`, { replace: true })
      } else {
        await examsApi.update(id, {
          title: exam.title,
          description: exam.description,
          strictness: exam.strictness,
          duration_min: exam.duration_min,
          status: exam.status,
        })
        await examsApi.replaceQuestions(id, payloadQs)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const copyCode = async () => {
    if (!code) return
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* ignore */
    }
  }

  return (
    <PageShell>
      <section className="mx-auto max-w-5xl px-6 pt-10 pb-16">
        <Link
          to="/proctor/exams"
          className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted hover:text-text-secondary"
        >
          <ArrowLeft size={11} strokeWidth={2} /> exams
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <h1 className="text-3xl font-medium tracking-tightest text-text-primary">
            {isNew ? 'New exam' : exam.title || 'Untitled'}
          </h1>
          {code && (
            <div>
              <p className="label">Join code</p>
              <div className="mt-1 flex items-center gap-2">
                <code className="font-mono text-2xl tracking-widest text-text-primary">
                  {code}
                </code>
                <button
                  type="button"
                  onClick={copyCode}
                  className="rounded border border-border p-2 text-text-muted hover:text-text-primary"
                  title="Copy code"
                >
                  {copied ? (
                    <Check size={14} className="text-accent" strokeWidth={2} />
                  ) : (
                    <Copy size={14} strokeWidth={2} />
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="mt-6 rounded border border-risk-high/40 bg-risk-high/5 p-3 text-[13px] text-risk-high">
            {error}
          </p>
        )}

        <div className="mt-8 grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <Card title="Details">
              <Field label="Title">
                <input
                  className="input w-full"
                  value={exam.title}
                  onChange={(e) => setExam({ ...exam, title: e.target.value })}
                  placeholder="Algorithms midterm"
                />
              </Field>
              <Field label="Description (optional)">
                <textarea
                  className="input w-full"
                  rows={2}
                  value={exam.description}
                  onChange={(e) =>
                    setExam({ ...exam, description: e.target.value })
                  }
                />
              </Field>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Strictness">
                  <select
                    className="input w-full"
                    value={exam.strictness}
                    onChange={(e) =>
                      setExam({ ...exam, strictness: e.target.value })
                    }
                  >
                    <option value="lenient">Lenient</option>
                    <option value="moderate">Moderate</option>
                    <option value="strict">Strict</option>
                  </select>
                </Field>
                <Field label="Duration (min)">
                  <input
                    type="number"
                    className="input w-full"
                    min={1}
                    max={240}
                    value={exam.duration_min}
                    onChange={(e) =>
                      setExam({
                        ...exam,
                        duration_min: parseInt(e.target.value, 10) || 1,
                      })
                    }
                  />
                </Field>
                {!isNew && (
                  <Field label="Status">
                    <select
                      className="input w-full"
                      value={exam.status}
                      onChange={(e) =>
                        setExam({ ...exam, status: e.target.value })
                      }
                    >
                      <option value="draft">Draft (not joinable)</option>
                      <option value="live">Live (accepting)</option>
                      <option value="closed">Closed</option>
                    </select>
                  </Field>
                )}
              </div>
            </Card>

            <Card title="Questions" right={`${questions.length} item${questions.length === 1 ? '' : 's'}`}>
              <ul className="space-y-3">
                <AnimatePresence initial={false}>
                  {questions.map((q, i) => (
                    <QuestionRow
                      key={i}
                      idx={i}
                      q={q}
                      onChange={(patch) => updateQuestion(i, patch)}
                      onRemove={() => removeQuestion(i)}
                    />
                  ))}
                </AnimatePresence>
              </ul>
              <button
                type="button"
                onClick={addQuestion}
                className="btn-secondary mt-4"
              >
                <Plus size={13} strokeWidth={2} /> Add question
              </button>
            </Card>

            <button
              type="button"
              onClick={onSave}
              disabled={busy}
              className="btn-primary disabled:opacity-50"
            >
              <Save size={13} strokeWidth={2} />{' '}
              {busy ? 'Saving…' : isNew ? 'Create exam' : 'Save changes'}
            </button>
          </div>

          {!isNew && (
            <div className="space-y-4 lg:col-span-1">
              <Card title="Attempts" right={`${attempts.length}`}>
                {attempts.length === 0 ? (
                  <p className="text-[12px] text-text-muted">
                    No attempts yet.
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {attempts.map((a) => (
                      <li key={a.id} className="flex items-center justify-between py-2 text-[12.5px]">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-text-primary">
                            {a.candidate_name}
                          </p>
                          <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                            {a.status}
                            {a.auto_score !== null &&
                              a.auto_score !== undefined && (
                                <>
                                  {' · '}
                                  {a.auto_score}/{a.max_auto_score}
                                </>
                              )}
                            {a.peak_risk !== null &&
                              a.peak_risk !== undefined && (
                                <>
                                  {' · risk '}
                                  {a.peak_risk}
                                </>
                              )}
                          </p>
                        </div>
                        {a.proctor_session_id && (
                          <a
                            href={`/proctor/session/${a.proctor_session_id}`}
                            className="text-text-muted hover:text-text-primary"
                            title="Open session in monitor"
                          >
                            <FileText size={13} strokeWidth={2} />
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}
        </div>
      </section>
    </PageShell>
  )
}

function blankQuestion(idx) {
  return {
    idx,
    kind: 'mcq',
    prompt: '',
    options: ['', '', '', ''],
    correct_index: 0,
    points: 1,
  }
}

function Card({ title, right, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded border border-border bg-surface-1 p-5"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          {title}
        </h2>
        {right && (
          <span className="font-mono text-[10px] text-text-muted">{right}</span>
        )}
      </div>
      <div className="space-y-3">{children}</div>
    </motion.div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="label mb-1.5 block">{label}</span>
      {children}
    </label>
  )
}

function QuestionRow({ idx, q, onChange, onRemove }) {
  return (
    <motion.li
      layout
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="rounded border border-border bg-surface-2 p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          Q{idx + 1}
        </span>
        <div className="flex items-center gap-2">
          <select
            className="input text-[12px]"
            value={q.kind}
            onChange={(e) =>
              onChange({
                kind: e.target.value,
                ...(e.target.value === 'short'
                  ? { options: null, correct_index: null }
                  : {
                      options: q.options || ['', '', '', ''],
                      correct_index: q.correct_index ?? 0,
                    }),
              })
            }
          >
            <option value="mcq">Multiple choice</option>
            <option value="short">Short answer</option>
          </select>
          <input
            type="number"
            min={1}
            max={20}
            value={q.points}
            onChange={(e) =>
              onChange({ points: parseInt(e.target.value, 10) || 1 })
            }
            className="input w-16 text-[12px]"
            title="Points"
          />
          <button
            type="button"
            onClick={onRemove}
            className="rounded border border-border p-2 text-text-muted hover:text-risk-high"
            title="Remove question"
          >
            <Trash2 size={13} strokeWidth={2} />
          </button>
        </div>
      </div>
      <textarea
        className="input mt-3 w-full"
        rows={2}
        placeholder="Question prompt…"
        value={q.prompt}
        onChange={(e) => onChange({ prompt: e.target.value })}
      />
      {q.kind === 'mcq' && (
        <div className="mt-3 space-y-2">
          {(q.options || []).map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="radio"
                checked={q.correct_index === i}
                onChange={() => onChange({ correct_index: i })}
                className="accent-accent"
                title="Mark as correct"
              />
              <input
                className="input flex-1 text-[13px]"
                placeholder={`Option ${String.fromCharCode(65 + i)}`}
                value={opt}
                onChange={(e) => {
                  const next = [...(q.options || [])]
                  next[i] = e.target.value
                  onChange({ options: next })
                }}
              />
              {(q.options || []).length > 2 && (
                <button
                  type="button"
                  onClick={() => {
                    const next = (q.options || []).filter((_, k) => k !== i)
                    let nextCorrect = q.correct_index
                    if (q.correct_index === i) nextCorrect = 0
                    else if (q.correct_index > i) nextCorrect = q.correct_index - 1
                    onChange({ options: next, correct_index: nextCorrect })
                  }}
                  className="rounded p-1.5 text-text-muted hover:text-risk-high"
                  title="Remove option"
                >
                  <Trash2 size={11} strokeWidth={2} />
                </button>
              )}
            </div>
          ))}
          {(q.options || []).length < 6 && (
            <button
              type="button"
              onClick={() =>
                onChange({ options: [...(q.options || []), ''] })
              }
              className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted hover:text-text-primary"
            >
              + add option
            </button>
          )}
        </div>
      )}
    </motion.li>
  )
}
