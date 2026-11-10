import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, LoaderCircle, TriangleAlert } from 'lucide-react'
import { api, errorMessage, listOf } from '../api/client.js'
import { formatDate, platformLabel } from '../lib/format.js'
import ReviewModal from './ReviewModal.jsx'

// Applications waiting for the user's confirmation (REQ-10), plus ones a CAPTCHA or an
// error stopped (REQ-13), so nothing is left half-done.
const WAITING = ['draft', 'manual_review_required', 'failed']

const STATUS = {
  draft: { label: 'Waiting for review', className: 'bg-blue-50 text-blue-700' },
  manual_review_required: { label: 'Manual review required', className: 'bg-amber-50 text-amber-800' },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700' },
}

export default function ReviewQueue({ onToast }) {
  const [apps, setApps] = useState(null)
  const [active, setActive] = useState(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let live = true
    Promise.all(WAITING.map((s) => api.get(`/applications/?status=${s}`)))
      .then((responses) => {
        if (!live) return
        const all = responses.flatMap(({ data }) => listOf(data))
        // Manual (assisted) applications are finished on the site, not submitted from here.
        setApps(all.filter((a) => a.method !== 'manual').sort((a, b) => b.created_at.localeCompare(a.created_at)))
      })
      .catch((err) => live && setError(errorMessage(err)))
    return () => {
      live = false
    }
  }, [reload])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Applications to Review</h1>
        <p className="mt-1 text-sm text-slate-600">
          Nothing is submitted until you confirm it. Start an application from the{' '}
          <Link to="/feed" className="text-blue-700 hover:underline">job feed</Link>.
        </p>
      </div>
      {error && <p role="alert" className="rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        {apps === null ? (
          <p role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-slate-600">
            <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
            Loading applications…
          </p>
        ) : apps.length === 0 ? (
          <p className="px-6 py-16 text-center text-sm text-slate-600">Nothing waiting for review.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {apps.map((app) => {
              const status = STATUS[app.status]
              return (
                <li key={app.id} className="flex flex-wrap items-center justify-between gap-3 p-5">
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900">{app.title}</p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-sm text-slate-600">
                      {app.company}
                      <span aria-hidden="true">·</span>
                      {platformLabel(app.platform)}
                      <span aria-hidden="true">·</span>
                      {formatDate(app.created_at)}
                    </p>
                    {app.result?.error && (
                      <p className="mt-1 flex items-center gap-1.5 text-sm text-red-700">
                        <TriangleAlert className="size-3.5" aria-hidden="true" />
                        {app.result.error}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${status.className}`}>{status.label}</span>
                    {app.status === 'manual_review_required' ? (
                      <a
                        href={app.posting_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <ExternalLink className="size-4" aria-hidden="true" />
                        Open posting
                      </a>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setActive(app)}
                        className="cursor-pointer rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                      >
                        {app.status === 'failed' ? 'Try again' : 'Review'}
                      </button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {active && (
        <ReviewModal
          key={active.id}
          application={active}
          onClose={() => setActive(null)}
          onSubmitted={(message) => {
            setActive(null)
            setReload((n) => n + 1)
            onToast(message)
          }}
        />
      )}
    </div>
  )
}
