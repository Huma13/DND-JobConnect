import { useEffect, useRef, useState } from 'react'
import { Building2, LoaderCircle, Mail, Paperclip, Shield, TriangleAlert, Workflow, X } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { platformLabel } from '../lib/format.js'

const inputClass =
  'mt-1.5 block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-shadow focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20 focus:outline-none'

const OUTCOME = {
  submitted: (app) => `Application submitted to ${app.company}`,
  manual_review_required: () =>
    'The site asked for a CAPTCHA. Automation stopped; finish this one yourself from the posting.',
}

// REQ-10: nothing is sent until the user has seen the content and confirmed it.
export default function ReviewModal({ application, onClose, onSubmitted }) {
  const dialogRef = useRef(null)
  const [review, setReview] = useState(null)
  const [coverLetter, setCoverLetter] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // The native <dialog> gives us the top layer, focus trapping and Escape.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog.open) dialog.showModal()
  }, [])

  useEffect(() => {
    let active = true
    api
      .get(`/applications/${application.id}/review/`)
      .then(({ data }) => {
        if (!active) return
        setReview(data)
        setCoverLetter(data.cover_letter)
      })
      .catch((err) => active && setError(errorMessage(err)))
    return () => {
      active = false
    }
  }, [application.id])

  function requestClose() {
    if (!submitting) onClose()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      if (coverLetter !== review.cover_letter) {
        await api.patch(`/applications/kits/${application.kit.id}/edit/`, { cover_letter: coverLetter })
      }
      const { data } = await api.post(`/applications/${application.id}/submit/`, { confirmed })
      const message = OUTCOME[data.status]
      if (message) {
        onSubmitted(message(data))
      } else {
        setError(data.result?.error ? `Not submitted: ${data.result.error}` : `Status: ${data.status}`)
        setSubmitting(false)
      }
    } catch (err) {
      setError(errorMessage(err))
      setSubmitting(false)
    }
  }

  const isEmail = application.method === 'email'
  const ChannelIcon = isEmail ? Mail : Workflow

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="review-modal-title"
      onCancel={(event) => {
        event.preventDefault()
        requestClose()
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) requestClose()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-xl bg-white p-0 shadow-xl transition duration-200 backdrop:bg-slate-900/60 backdrop:backdrop-blur-sm starting:translate-y-2 starting:opacity-0"
    >
      <form onSubmit={handleSubmit}>
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
          <div>
            <h2 id="review-modal-title" className="text-lg font-semibold text-slate-900">
              Review Application
            </h2>
            <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-sm text-slate-600">
              <span className="font-medium text-slate-900">{application.title}</span>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <Building2 className="size-3.5" aria-hidden="true" />
                {application.company}
              </span>
            </p>
          </div>
          <button
            type="button"
            onClick={requestClose}
            aria-label="Close"
            disabled={submitting}
            className="cursor-pointer rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        <div className="space-y-4 px-6 py-5">
          {!review && !error ? (
            <p role="status" className="flex items-center justify-center gap-2 py-8 text-sm text-slate-600">
              <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
              Loading application…
            </p>
          ) : review && (
            <>
              <p className="flex items-center gap-2 text-sm text-slate-700">
                <ChannelIcon className="size-4 text-blue-700" aria-hidden="true" />
                {isEmail ? (
                  <>Sends by email to <span className="font-medium text-slate-900">{review.to_email}</span></>
                ) : (
                  <>Submits on the {platformLabel(review.platform)} career page</>
                )}
              </p>

              <label className="block text-sm font-medium text-slate-700">
                Cover letter
                <textarea
                  rows={7}
                  value={coverLetter}
                  onChange={(event) => setCoverLetter(event.target.value)}
                  disabled={submitting}
                  className={inputClass}
                />
              </label>

              <div>
                <p className="text-sm font-medium text-slate-700">Attachment</p>
                <div className="mt-1.5 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5">
                  <Paperclip className="size-4 text-slate-500" aria-hidden="true" />
                  <span className="text-sm font-medium text-slate-900">Tailored resume</span>
                  <span className="ml-auto text-xs text-slate-500 tabular-nums">
                    {review.resume_text.split('\n').length} lines
                  </span>
                </div>
              </div>

              <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3.5" role="note">
                <Shield className="mt-0.5 size-5 shrink-0 text-amber-700" aria-hidden="true" />
                <p className="text-sm text-amber-900">
                  {review.requires_confirmation
                    ? 'Nothing is sent until you confirm. Full-Auto is off for this channel.'
                    : 'Full-Auto is on for this channel, so confirmation is optional.'}
                </p>
              </div>

              <label className="flex items-start gap-2.5 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  className="mt-0.5 size-4 rounded border-slate-300 text-blue-600"
                />
                I have reviewed this application and want it sent.
              </label>
            </>
          )}

          {error && (
            <p role="alert" className="flex gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {error}
            </p>
          )}
        </div>

        <footer className="flex flex-col-reverse gap-3 rounded-b-xl border-t border-slate-200 bg-slate-50 px-6 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={requestClose}
            disabled={submitting}
            className="cursor-pointer rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !review || (review.requires_confirmation && !confirmed)}
            aria-busy={submitting}
            className="inline-flex min-w-40 cursor-pointer items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
            {submitting ? 'Submitting…' : 'Confirm & Apply'}
          </button>
        </footer>
      </form>
    </dialog>
  )
}
