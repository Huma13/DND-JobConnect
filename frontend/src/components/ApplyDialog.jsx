import { useEffect, useRef, useState } from 'react'
import { Building2, CircleCheck, Download, ExternalLink, LoaderCircle, Mail, MousePointerClick, Workflow, X } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { atsFor, platformLabel } from '../lib/format.js'
import ReviewModal from './ReviewModal.jsx'

// The three application channels from the architecture document (section 2.1).
function channelsFor(item) {
  const channels = []
  const ats = atsFor(item.url)
  if (ats) {
    channels.push({ method: 'ats', icon: Workflow, title: `Apply on the ${platformLabel(ats)} career page`,
      text: 'Fills and submits the standard form after you review it.' })
  }
  if (item.platform === 'linkedin' || item.platform === 'naukri') {
    channels.push({ method: 'manual', icon: MousePointerClick, title: `Assisted apply on ${platformLabel(item.platform)}`,
      text: `${platformLabel(item.platform)} does not allow automated applications. We prepare your kit and open the posting; you submit it.` })
  }
  channels.push({ method: 'email', icon: Mail, title: 'Apply by email',
    text: 'Sends your tailored resume and cover letter from your own mailbox after you review it.' })
  return channels
}

async function download(kitId, part) {
  const { data } = await api.get(`/applications/kits/${kitId}/download/?part=${part}`, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = part === 'resume' ? 'resume.txt' : 'cover-letter.txt'
  link.click()
  URL.revokeObjectURL(url)
}

function Kit({ kit }) {
  const [tab, setTab] = useState('resume')
  const tabs = [
    ['resume', 'Resume'],
    ['cover', 'Cover letter'],
    ['answers', 'Answers'],
  ]
  return (
    <div className="rounded-lg border border-slate-200">
      <div className="flex items-center gap-1 border-b border-slate-200 px-2 pt-2" role="tablist">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`rounded-t-md px-3 py-1.5 text-sm font-medium ${tab === key ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-800'}`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto flex gap-1 pb-1.5">
          <button type="button" onClick={() => download(kit.id, 'resume')} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100">
            <Download className="size-3.5" aria-hidden="true" /> Resume
          </button>
          <button type="button" onClick={() => download(kit.id, 'cover_letter')} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100">
            <Download className="size-3.5" aria-hidden="true" /> Cover letter
          </button>
        </span>
      </div>
      <div className="max-h-64 overflow-y-auto p-4 text-sm text-slate-800">
        {tab === 'resume' && <pre className="font-sans whitespace-pre-wrap">{kit.resume_text}</pre>}
        {tab === 'cover' && <pre className="font-sans whitespace-pre-wrap">{kit.cover_letter}</pre>}
        {tab === 'answers' && (
          <dl className="space-y-3">
            {Object.entries(kit.answers).map(([q, a]) => (
              <div key={q}>
                <dt className="font-medium text-slate-900">{q}</dt>
                <dd className="mt-0.5 text-slate-700">{a || '—'}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>
  )
}

export default function ApplyDialog({ item, onClose, onDone }) {
  const dialogRef = useRef(null)
  const channels = channelsFor(item)
  const [method, setMethod] = useState(channels[0].method)
  const [toEmail, setToEmail] = useState('')
  const [needsEmail, setNeedsEmail] = useState(false)
  const [application, setApplication] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
  }, [application])

  async function start() {
    setBusy(true)
    setError('')
    try {
      const body = { feed_item: item.id, method }
      if (method === 'email' && toEmail.trim()) body.to_email = toEmail.trim()
      const { data } = await api.post('/applications/', body)
      setApplication(data)
    } catch (err) {
      if (err.response?.data?.to_email) setNeedsEmail(true)
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function markApplied() {
    setBusy(true)
    setError('')
    try {
      await api.post(`/applications/${application.id}/mark-applied/`)
      onDone(`Marked as applied: ${item.title} at ${item.company}`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  // Career-page and email applications go through the review-before-submit step (REQ-10).
  if (application && application.method !== 'manual') {
    return <ReviewModal application={application} onClose={() => onDone()} onSubmitted={onDone} />
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="apply-title"
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onClose()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-2xl rounded-xl bg-white p-0 shadow-xl backdrop:bg-slate-900/60 backdrop:backdrop-blur-sm"
    >
      <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
        <div>
          <h2 id="apply-title" className="text-lg font-semibold text-slate-900">Apply</h2>
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-sm text-slate-600">
            <span className="font-medium text-slate-900">{item.title}</span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <Building2 className="size-3.5" aria-hidden="true" />
              {item.company}
            </span>
          </p>
        </div>
        <button type="button" onClick={onClose} disabled={busy} aria-label="Close" className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100">
          <X className="size-5" aria-hidden="true" />
        </button>
      </header>

      <div className="space-y-4 px-6 py-5">
        {!application ? (
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm font-medium text-slate-700">How do you want to apply?</legend>
            {channels.map(({ method: m, icon: Icon, title, text }) => (
              <label
                key={m}
                className={`flex cursor-pointer gap-3 rounded-lg border p-3.5 ${method === m ? 'border-blue-600 bg-blue-50/50 ring-1 ring-blue-600' : 'border-slate-200 hover:border-slate-300'}`}
              >
                <input type="radio" name="method" value={m} checked={method === m} onChange={() => setMethod(m)} className="sr-only" />
                <Icon className="mt-0.5 size-5 shrink-0 text-blue-700" aria-hidden="true" />
                <span>
                  <span className="block text-sm font-medium text-slate-900">{title}</span>
                  <span className="block text-sm text-slate-600">{text}</span>
                </span>
              </label>
            ))}
            {method === 'email' && (
              <label className="block pt-2 text-sm font-medium text-slate-700">
                Recruiter email {needsEmail ? '' : <span className="font-normal text-slate-500">(optional if the posting lists one)</span>}
                <input
                  type="email"
                  value={toEmail}
                  onChange={(e) => setToEmail(e.target.value)}
                  placeholder="careers@company.com"
                  className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
                />
              </label>
            )}
          </fieldset>
        ) : (
          <>
            <p className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-900">
              <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              Your application kit is ready. Open the posting, apply using the kit below, then come back and mark it as applied.
            </p>
            <Kit kit={application.kit} />
          </>
        )}
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>

      <footer className="flex flex-col-reverse gap-3 rounded-b-xl border-t border-slate-200 bg-slate-50 px-6 py-4 sm:flex-row sm:justify-end">
        <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
          {application ? 'Close' : 'Cancel'}
        </button>
        {!application ? (
          <button type="button" onClick={start} disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
            {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
            Prepare application
          </button>
        ) : (
          <>
            <a href={application.posting_url} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center gap-2 rounded-lg border border-blue-600 px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50">
              <ExternalLink className="size-4" aria-hidden="true" />
              Open posting
            </a>
            <button type="button" onClick={markApplied} disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
              {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
              I've applied
            </button>
          </>
        )}
      </footer>
    </dialog>
  )
}
