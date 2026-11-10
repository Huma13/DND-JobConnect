import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CircleCheck, ExternalLink, Gauge, LoaderCircle, Send, TriangleAlert, Wand2 } from 'lucide-react'
import { api, errorMessage, listOf } from '../api/client.js'
import { platformLabel } from '../lib/format.js'

const CHANNELS = { linkedin_note: 'LinkedIn note', x_message: 'X message' }
const channelPlatform = (channel) => (channel === 'x_message' ? 'x' : 'linkedin')

// How many top feed items to check for recruiter contacts when no posting is chosen.
const SCAN_ITEMS = 20

function initials(name) {
  return name
    .replace('@', '')
    .split(/[\s_]+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

const primaryButtonClass =
  'inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60'
const secondaryButtonClass =
  'inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60'

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
                <span className="block text-sm font-semibold text-slate-900">{recruiter.name}</span>
                <span className="block truncate text-sm text-slate-600">
                  {recruiter.job.title} · {recruiter.job.company}
                </span>
              </span>
              {sentIds.includes(recruiter.id) && (
                <CircleCheck className="size-5 shrink-0 text-emerald-600" aria-label="Message sent" />
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function CapNote({ limit }) {
  if (!limit) return <span />
  return (
    <p className="flex items-center gap-2 text-sm text-slate-600">
      <Gauge className="size-4 text-slate-500" aria-hidden="true" />
      <span className="tabular-nums">
        Daily {platformLabel(limit.platform)} outreach cap: {limit.sent_today}/{limit.daily_limit} used today
      </span>
    </p>
  )
}

/* ------------------------------- Main screen ----------------------------- */

export default function OutreachPanel({ onToast }) {
  const [params] = useSearchParams()
  const feedItem = params.get('feed_item')
  const [recruiters, setRecruiters] = useState(null)
  const [messages, setMessages] = useState({})
  const [limits, setLimits] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadLimits = useCallback(() => {
    api.get('/outreach/limits/').then(({ data }) => setLimits(data)).catch(() => {})
  }, [])

  // REQ-14: recruiters come from the postings themselves (X poster, LinkedIn profiles listed).
  useEffect(() => {
    let active = true
    async function load() {
      try {
        const items = feedItem
          ? [(await api.get(`/jobs/feed/${feedItem}/`)).data]
          : listOf((await api.get("/jobs/feed/")).data).slice(0, SCAN_ITEMS)
        const found = await Promise.all(
          items.map((item) =>
            api.get(`/outreach/recruiters/?feed_item=${item.id}`).then(({ data }) =>
              data.map((r) => ({ ...r, job: { title: item.title, company: item.company } })),
            ),
          ),
        )
        const { data: existing } = await api.get('/outreach/messages/')
        if (!active) return
        const list = found.flat()
        const byRecruiter = {}
        listOf(existing).forEach((m) => {
          byRecruiter[m.recruiter] ??= m
        })
        setRecruiters(list)
        setMessages(byRecruiter)
        if (list.length) {
          setSelectedId(list[0].id)
          setBody(byRecruiter[list[0].id]?.body ?? '')
        }
      } catch (err) {
        if (active) {
          setError(errorMessage(err))
          setRecruiters([])
        }
      }
    }
    load()
    loadLimits()
    return () => {
      active = false
    }
  }, [feedItem, loadLimits])

  const recruiter = recruiters?.find((r) => r.id === selectedId)
  const message = recruiter ? messages[recruiter.id] : null
  const isSent = message?.status === 'sent'
  const sentIds = Object.values(messages).filter((m) => m.status === 'sent').map((m) => m.recruiter)
  const limit = limits.find((l) => l.platform === (message?.platform || channelPlatform(recruiter?.best_channel)))
  const capReached = limit && limit.sent_today >= limit.daily_limit

  function select(id) {
    setSelectedId(id)
    setBody(messages[id]?.body ?? '')
    setError('')
  }

  function store(msg) {
    setMessages((current) => ({ ...current, [msg.recruiter]: msg }))
    setBody(msg.body)
  }

  // REQ-15: a personalised draft from the posting and the user's skills.
  async function draft() {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/outreach/messages/', {
        recruiter: recruiter.id,
        platform: channelPlatform(recruiter.best_channel),
      })
      store(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function saveEdits() {
    if (message && body !== message.body) {
      const { data } = await api.patch(`/outreach/messages/${message.id}/`, { body })
      store(data)
    }
  }

  async function send(action) {
    setBusy(true)
    setError('')
    try {
      await saveEdits()
      const { data } = await api.post(`/outreach/messages/${message.id}/${action}/`)
      store(data)
      loadLimits()
      if (data.status === 'failed') setError(`Not sent: ${data.detail}`)
      else onToast(`Message to ${recruiter.name} recorded as sent`)
    } catch (err) {
      // REQ-17: the same text to a second recipient comes back as 409.
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Recruiter Outreach</h1>
        <p className="mt-1 text-sm text-slate-600">
          {feedItem ? 'Recruiters for the posting you chose. ' : 'Recruiters found in your top matches. '}
          Review and personalize each message before it goes out.
          {feedItem && (
            <>
              {' '}
              <Link to="/outreach" className="text-blue-700 hover:underline">Show all</Link>
            </>
          )}
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
      ) : recruiters.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-6 py-16 text-center text-sm text-slate-600 shadow-sm">
          <p className="font-medium text-slate-900">No recruiter contacts found</p>
          <p className="mt-1">
            Recruiters are suggested when a posting names a LinkedIn profile or an X account.
          </p>
          {error && <p className="mt-3 text-red-700">{error}</p>}
        </div>
      ) : (
        <div className="grid overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[22rem_1fr]">
          <aside className="border-b border-slate-200 lg:border-r lg:border-b-0">
            <h2 className="px-6 pt-5 text-sm font-semibold text-slate-900">Suggested Recruiters</h2>
            <RecruiterList recruiters={recruiters} selectedId={selectedId} sentIds={sentIds} locked={busy} onSelect={select} />
          </aside>

          <section className="flex flex-col p-6" aria-label="Message composer">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-base font-semibold text-slate-900">{recruiter.name}</h2>
                <p className="mt-0.5 text-sm text-slate-600">{recruiter.reason}</p>
              </div>
              <p className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                Best channel: {CHANNELS[recruiter.best_channel] || recruiter.best_channel}
              </p>
            </div>

            {!message ? (
              <div className="mt-6 flex flex-1 flex-col items-start gap-3">
                <p className="text-sm text-slate-600">
                  We'll write a short note that mentions the {recruiter.job.title} role and the skills of yours it asks for.
                </p>
                <button type="button" onClick={draft} disabled={busy} className={primaryButtonClass}>
                  {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Wand2 className="size-4" aria-hidden="true" />}
                  Draft a personalised message
                </button>
              </div>
            ) : (
              <>
                <label htmlFor="outreach-message" className="mt-5 mb-1.5 text-sm font-medium text-slate-700">
                  Your message {message.platform === 'linkedin' && <span className="font-normal text-slate-500">(LinkedIn notes are limited to 300 characters · {body.length}/300)</span>}
                </label>
                <textarea
                  id="outreach-message"
                  rows={7}
                  value={body}
                  readOnly={isSent || busy}
                  onChange={(event) => setBody(event.target.value)}
                  className="w-full flex-1 resize-none rounded-xl border border-slate-300 bg-white p-4 text-sm leading-6 text-slate-900 shadow-sm transition-shadow read-only:bg-slate-50 read-only:text-slate-600 focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20 focus:outline-none"
                />
              </>
            )}

            {error && (
              <p role="alert" className="mt-4 flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {error}
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <CapNote limit={limit} />
              {message && (isSent ? (
                <p className="inline-flex items-center gap-2 py-2.5 text-sm font-medium text-emerald-700">
                  <CircleCheck className="size-4" aria-hidden="true" />
                  Sent
                </p>
              ) : message.platform === 'linkedin' ? (
                // LinkedIn does not allow automated messages: the user sends the note from the profile.
                <div className="flex flex-wrap gap-2">
                  <a href={message.open_url} target="_blank" rel="noreferrer" className={secondaryButtonClass} onClick={saveEdits}>
                    <ExternalLink className="size-4" aria-hidden="true" />
                    Open LinkedIn profile
                  </a>
                  <button type="button" onClick={() => send('mark-sent')} disabled={busy || capReached || !body.trim()} className={primaryButtonClass}>
                    {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <CircleCheck className="size-4" aria-hidden="true" />}
                    I've sent it
                  </button>
                </div>
              ) : (
                <button type="button" onClick={() => send('send')} disabled={busy || capReached || !body.trim()} className={primaryButtonClass}>
                  {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
                  Send on X
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
