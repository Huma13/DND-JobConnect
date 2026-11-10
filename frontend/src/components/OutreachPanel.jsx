import { useEffect, useState } from 'react'
import { CircleCheck, Gauge, LoaderCircle, RotateCcw, Send } from 'lucide-react'

/* ------------------------------- Mock data ------------------------------- */

const MOCK_RECRUITERS = [
  {
    id: 1,
    name: 'Sarah Jenkins',
    role: 'Tech Recruiter',
    company: 'Google',
    platform: 'LinkedIn',
    jobTitle: 'Senior Frontend Engineer',
    skills: ['React', 'TypeScript'],
  },
  {
    id: 2,
    name: 'Mike Ross',
    role: 'Hiring Manager',
    company: 'Stripe',
    platform: 'LinkedIn',
    jobTitle: 'Full Stack Engineer',
    skills: ['Django', 'PostgreSQL'],
  },
  {
    id: 3,
    name: 'Priya Nair',
    role: 'Talent Partner',
    company: 'Atlassian',
    platform: 'X/Twitter',
    jobTitle: 'Platform Engineer',
    skills: ['Python', 'Docker'],
  },
]

const MESSAGE_TEMPLATE =
  "Hi [Name], I saw you are hiring for [Job Title] at [Company]. My background in [Skill 1] and [Skill 2] aligns perfectly with the role. I'd love to connect!"

const DAILY_CAP = 15
const USED_TODAY = 5

/* -------------------------------- Helpers -------------------------------- */

function buildMessage(recruiter) {
  return MESSAGE_TEMPLATE.replace('[Name]', recruiter.name.split(' ')[0])
    .replace('[Job Title]', recruiter.jobTitle)
    .replace('[Company]', recruiter.company)
    .replace('[Skill 1]', recruiter.skills[0])
    .replace('[Skill 2]', recruiter.skills[1])
}

function initials(name) {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
}

const primaryButtonClass =
  'inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60'

/* ------------------------------ Subcomponents ---------------------------- */

function Avatar({ name }) {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
      {initials(name)}
    </span>
  )
}

function RecruiterList({ recruiters, selectedId, sentIds, locked, onSelect }) {
  return (
    <ul className="space-y-1 p-3">
      {recruiters.map((recruiter) => {
        const selected = recruiter.id === selectedId
        return (
          <li key={recruiter.id}>
            <button
              type="button"
              aria-pressed={selected}
              disabled={locked}
              onClick={() => onSelect(recruiter.id)}
              className={`flex w-full cursor-pointer items-center gap-3 rounded-xl p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed ${
                selected ? 'bg-blue-50 ring-1 ring-blue-200' : 'hover:bg-slate-50'
              }`}
            >
              <Avatar name={recruiter.name} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-slate-900">
                  {recruiter.name}
                </span>
                <span className="block text-sm text-slate-600">
                  {recruiter.role} at {recruiter.company}
                </span>
              </span>
              {sentIds.includes(recruiter.id) && (
                <CircleCheck className="size-5 shrink-0 text-emerald-600" aria-label="Request sent" />
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function CapNote({ used }) {
  return (
    <p className="flex items-center gap-2 text-sm text-slate-600">
      <Gauge className="size-4 text-slate-500" aria-hidden="true" />
      <span className="tabular-nums">
        Daily Outreach Cap: {used}/{DAILY_CAP} used today
      </span>
    </p>
  )
}

/* ------------------------------- Main screen ----------------------------- */

export default function OutreachPanel({ onToast }) {
  const [recruiters, setRecruiters] = useState(null)
  const [selectedId, setSelectedId] = useState(MOCK_RECRUITERS[0].id)
  const [drafts, setDrafts] = useState({})
  const [sentIds, setSentIds] = useState([])
  const [usedToday, setUsedToday] = useState(USED_TODAY)
  const [confirming, setConfirming] = useState(false)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setRecruiters(MOCK_RECRUITERS), 800)
    return () => clearTimeout(timer)
  }, [])

  const recruiter = MOCK_RECRUITERS.find((item) => item.id === selectedId)
  const suggested = buildMessage(recruiter)
  const message = drafts[selectedId] ?? suggested
  const isSent = sentIds.includes(selectedId)
  const capReached = usedToday >= DAILY_CAP

  function handleSelect(id) {
    setSelectedId(id)
    setConfirming(false)
  }

  function handleEdit(text) {
    setDrafts((current) => ({ ...current, [selectedId]: text }))
    setConfirming(false)
  }

  function handleSend() {
    setSending(true)
    setTimeout(() => {
      setSending(false)
      setConfirming(false)
      setSentIds((ids) => [...ids, recruiter.id])
      setUsedToday((count) => count + 1)
      onToast(`Connection request sent to ${recruiter.name}`)
    }, 1400)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Recruiter Outreach</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review and personalize each request before it goes out.
        </p>
      </div>

      {recruiters === null ? (
        <p
          role="status"
          className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-40 text-sm text-slate-600 shadow-sm"
        >
          <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
          Finding recruiters for your matches…
        </p>
      ) : (
        <div className="grid overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[22rem_1fr]">
          <aside className="border-b border-slate-200 lg:border-r lg:border-b-0">
            <h2 className="px-6 pt-5 text-sm font-semibold text-slate-900">
              Suggested Recruiters
            </h2>
            <RecruiterList
              recruiters={recruiters}
              selectedId={selectedId}
              sentIds={sentIds}
              locked={sending}
              onSelect={handleSelect}
            />
          </aside>

          <section className="flex flex-col p-6" aria-label="Message composer">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-base font-semibold text-slate-900">{recruiter.name}</h2>
                <p className="mt-0.5 text-sm text-slate-600">
                  {recruiter.role} at {recruiter.company} · via {recruiter.platform}
                </p>
              </div>
              <p className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                {recruiter.jobTitle}
              </p>
            </div>

            <div className="mt-5 mb-1.5 flex items-center justify-between gap-3">
              <label htmlFor="outreach-message" className="text-sm font-medium text-slate-700">
                Your message
              </label>
              {message !== suggested && !isSent && (
                <button
                  type="button"
                  onClick={() => handleEdit(suggested)}
                  className="inline-flex cursor-pointer items-center gap-1.5 rounded text-sm font-medium text-blue-700 hover:text-blue-800 focus-visible:outline-2 focus-visible:outline-blue-600"
                >
                  <RotateCcw className="size-3.5" aria-hidden="true" />
                  Reset to suggested
                </button>
              )}
            </div>
            <textarea
              id="outreach-message"
              rows={7}
              value={message}
              readOnly={isSent || sending}
              onChange={(event) => handleEdit(event.target.value)}
              className="w-full flex-1 resize-none rounded-xl border border-slate-300 bg-white p-4 text-sm leading-6 text-slate-900 shadow-sm transition-shadow read-only:bg-slate-50 read-only:text-slate-600 focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20 focus:outline-none"
            />

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <CapNote used={usedToday} />

              {isSent ? (
                <p className="inline-flex items-center gap-2 py-2.5 text-sm font-medium text-emerald-700">
                  <CircleCheck className="size-4" aria-hidden="true" />
                  Request sent
                </p>
              ) : confirming ? (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm font-medium text-slate-900">
                    Send to {recruiter.name}?
                  </span>
                  <button
                    type="button"
                    onClick={() => setConfirming(false)}
                    disabled={sending}
                    className="cursor-pointer rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={sending}
                    aria-busy={sending}
                    className={primaryButtonClass}
                  >
                    {sending ? (
                      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Send className="size-4" aria-hidden="true" />
                    )}
                    {sending ? 'Sending…' : 'Confirm & Send'}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirming(true)}
                  disabled={!message.trim() || capReached}
                  className={primaryButtonClass}
                >
                  <Send className="size-4" aria-hidden="true" />
                  Send Personalized Request
                </button>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
