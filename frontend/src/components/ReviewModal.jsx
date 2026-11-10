import { useEffect, useRef, useState } from 'react'
import { Building2, LoaderCircle, Paperclip, Shield, X } from 'lucide-react'

/* ------------------------------- Mock data ------------------------------- */

const MOCK_APPLICANT = {
  fullName: 'Aarav Sharma',
  email: 'aarav.sharma@example.com',
  resume: { name: 'Resume.pdf', size: '248 KB' },
}

/* --------------------------------- Modal --------------------------------- */

const inputClass =
  'mt-1.5 block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-shadow focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20 focus:outline-none'

export default function ReviewModal({ job, onClose, onConfirmed }) {
  const dialogRef = useRef(null)
  const [fullName, setFullName] = useState(MOCK_APPLICANT.fullName)
  const [email, setEmail] = useState(MOCK_APPLICANT.email)
  const [submitting, setSubmitting] = useState(false)

  // The native <dialog> gives us the top layer, focus trapping and Escape.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog.open) dialog.showModal()
  }, [])

  function requestClose() {
    if (!submitting) onClose()
  }

  function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setTimeout(() => onConfirmed(job), 1600)
  }

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
              <span className="font-medium text-slate-900">{job.title}</span>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <Building2 className="size-3.5" aria-hidden="true" />
                {job.company}
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
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">
              Full Name
              <input
                type="text"
                required
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                disabled={submitting}
                className={inputClass}
              />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={submitting}
                className={inputClass}
              />
            </label>
          </div>

          <div>
            <p className="text-sm font-medium text-slate-700">Attachment</p>
            <div className="mt-1.5 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5">
              <Paperclip className="size-4 text-slate-500" aria-hidden="true" />
              <span className="text-sm font-medium text-slate-900">
                {MOCK_APPLICANT.resume.name}
              </span>
              <span className="ml-auto text-xs text-slate-500 tabular-nums">
                {MOCK_APPLICANT.resume.size}
              </span>
            </div>
          </div>

          <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3.5" role="note">
            <Shield className="mt-0.5 size-5 shrink-0 text-amber-700" aria-hidden="true" />
            <p className="text-sm text-amber-900">
              Automation uses your platform credentials. Explicit confirmation is required
              unless Full-Auto is enabled.
            </p>
          </div>
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
            disabled={submitting}
            aria-busy={submitting}
            className="inline-flex min-w-40 cursor-pointer items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-80"
          >
            {submitting && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
            {submitting ? 'Submitting…' : 'Confirm & Apply'}
          </button>
        </footer>
      </form>
    </dialog>
  )
}
