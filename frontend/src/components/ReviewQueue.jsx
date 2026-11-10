import { useEffect, useState } from 'react'
import { CircleCheck, LoaderCircle, MapPin } from 'lucide-react'
import ReviewModal from './ReviewModal.jsx'

/* ------------------------------- Mock data ------------------------------- */

const MOCK_PENDING_JOBS = [
  { id: 1, title: 'Software Engineer II', company: 'Microsoft', platform: 'LinkedIn', location: 'Hyderabad', score: 92 },
  { id: 2, title: 'Full Stack Developer', company: 'Freshworks', platform: 'Naukri', location: 'Chennai', score: 86 },
  { id: 3, title: 'Backend Engineer', company: 'CRED', platform: 'X/Twitter', location: 'Bengaluru', score: 81 },
]

/* ------------------------------- Main screen ----------------------------- */

// Page behind the modal: opens the first job on arrival so the demo lands on it.
export default function ReviewQueue({ onToast }) {
  const [jobs, setJobs] = useState(null)
  const [activeJob, setActiveJob] = useState(null)
  const [submittedIds, setSubmittedIds] = useState([])

  useEffect(() => {
    const timer = setTimeout(() => {
      setJobs(MOCK_PENDING_JOBS)
      setActiveJob(MOCK_PENDING_JOBS[0])
    }, 700)
    return () => clearTimeout(timer)
  }, [])

  function handleConfirmed(job) {
    setActiveJob(null)
    setSubmittedIds((ids) => [...ids, job.id])
    onToast(`Application submitted to ${job.company}`)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Applications to Review
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Nothing is submitted until you confirm it.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        {jobs === null ? (
          <p role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-slate-600">
            <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
            Loading matched jobs…
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {jobs.map((job) => (
              <li key={job.id} className="flex flex-wrap items-center justify-between gap-3 p-5">
                <div>
                  <p className="font-medium text-slate-900">{job.title}</p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-sm text-slate-600">
                    {job.company}
                    <span aria-hidden="true">·</span>
                    {job.platform}
                    <span aria-hidden="true">·</span>
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" aria-hidden="true" />
                      {job.location}
                    </span>
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 tabular-nums ring-1 ring-emerald-600/20 ring-inset">
                    {job.score}
                  </span>
                  {submittedIds.includes(job.id) ? (
                    <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700">
                      <CircleCheck className="size-4" aria-hidden="true" />
                      Applied
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setActiveJob(job)}
                      className="cursor-pointer rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                    >
                      Review
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {activeJob && (
        <ReviewModal
          key={activeJob.id}
          job={activeJob}
          onClose={() => setActiveJob(null)}
          onConfirmed={handleConfirmed}
        />
      )}
    </div>
  )
}
