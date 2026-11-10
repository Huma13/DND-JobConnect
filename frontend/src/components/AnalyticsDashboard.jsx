import { useEffect, useState } from 'react'
import {
  CalendarCheck,
  CircleCheck,
  Download,
  Eye,
  FileText,
  LoaderCircle,
  MessageSquareReply,
  Send,
  TriangleAlert,
  XCircle,
} from 'lucide-react'

/* ------------------------------- Mock data ------------------------------- */

const MOCK_KPIS = [
  {
    label: 'Total Applications',
    value: '144',
    caption: 'Across 3 platforms',
    icon: FileText,
  },
  {
    label: 'Interviews Scheduled',
    value: '18',
    caption: 'From tracked applications',
    icon: CalendarCheck,
  },
  {
    label: 'Response Rate (%)',
    value: '12.5%',
    caption: 'Interviews or replies ÷ applications',
    icon: MessageSquareReply,
  },
]

const MOCK_PLATFORMS = [
  { name: 'Naukri', count: 62 },
  { name: 'LinkedIn', count: 60 },
  { name: 'X/Twitter', count: 20 },
]

const MOCK_HISTORY = [
  { id: 1, title: 'Senior Frontend Engineer', company: 'Google', platform: 'LinkedIn', score: 94, date: '2026-11-09', status: 'Interview' },
  { id: 2, title: 'Backend Developer (Django)', company: 'Razorpay', platform: 'Naukri', score: 88, date: '2026-11-09', status: 'Applied' },
  { id: 3, title: 'Full Stack Engineer', company: 'Stripe', platform: 'LinkedIn', score: 91, date: '2026-11-08', status: 'Interview' },
  { id: 4, title: 'Software Development Engineer II', company: 'Flipkart', platform: 'Naukri', score: 79, date: '2026-11-08', status: 'Manual Review Required' },
  { id: 5, title: 'Platform Engineer', company: 'Atlassian', platform: 'LinkedIn', score: 85, date: '2026-11-07', status: 'Viewed' },
  { id: 6, title: 'React Developer', company: 'Zoho', platform: 'Naukri', score: 72, date: '2026-11-06', status: 'Applied' },
  { id: 7, title: 'DevOps Engineer', company: 'Postman', platform: 'X/Twitter', score: 64, date: '2026-11-05', status: 'Rejected' },
  { id: 8, title: 'Product Engineer', company: 'Swiggy', platform: 'X/Twitter', score: 76, date: '2026-11-04', status: 'Offer' },
]

/* --------------------------------- Styles -------------------------------- */

const STATUS_STYLES = {
  Applied: { className: 'bg-blue-50 text-blue-700', icon: Send },
  Viewed: { className: 'bg-indigo-50 text-indigo-700', icon: Eye },
  Interview: { className: 'bg-emerald-50 text-emerald-700', icon: CalendarCheck },
  Offer: { className: 'bg-emerald-100 text-emerald-800', icon: CircleCheck },
  Rejected: { className: 'bg-slate-100 text-slate-700', icon: XCircle },
  'Manual Review Required': { className: 'bg-amber-50 text-amber-800', icon: TriangleAlert },
}

function scoreBadgeClass(score) {
  if (score >= 85) return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
  if (score >= 70) return 'bg-blue-50 text-blue-700 ring-blue-600/20'
  return 'bg-amber-50 text-amber-800 ring-amber-600/20'
}

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
})

const panelClass = 'rounded-xl border border-slate-200 bg-white shadow-sm'

/* ------------------------------ Subcomponents ---------------------------- */

function KpiCard({ label, value, caption, icon: Icon }) {
  return (
    <div className={`${panelClass} p-5`}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-600">{label}</p>
        <span className="flex size-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
          <Icon className="size-5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">
        {value}
      </p>
      <p className="mt-1 text-sm text-slate-500">{caption}</p>
    </div>
  )
}

function PlatformChart({ platforms }) {
  const max = Math.max(...platforms.map((platform) => platform.count))
  const total = platforms.reduce((sum, platform) => sum + platform.count, 0)

  return (
    <ul className="space-y-1">
      {platforms.map(({ name, count }) => {
        const width = `${(count / max) * 100}%`
        const share = ((count / total) * 100).toFixed(1)

        return (
          <li
            key={name}
            className="group grid grid-cols-[5rem_1fr_2rem] items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-slate-50 sm:grid-cols-[6rem_1fr_2.5rem]"
          >
            <span className="text-sm text-slate-700">{name}</span>
            <div className="relative h-3">
              <div
                className="h-full origin-left rounded-r bg-blue-600 transition duration-700 ease-out starting:scale-x-0"
                style={{ width }}
              />
              <div
                className="pointer-events-none absolute bottom-full z-10 mb-2 -translate-x-full rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs whitespace-nowrap text-white opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
                style={{ left: width }}
                role="tooltip"
              >
                {count} applications · {share}% of total
              </div>
            </div>
            <span className="text-right text-sm font-semibold text-slate-900 tabular-nums">
              {count}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function ScoreBadge({ score }) {
  return (
    <span
      className={`inline-flex min-w-10 justify-center rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums ring-1 ring-inset ${scoreBadgeClass(score)}`}
    >
      {score}
    </span>
  )
}

function StatusBadge({ status }) {
  const { className, icon: Icon } = STATUS_STYLES[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap ${className}`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {status}
    </span>
  )
}

function HistoryTable({ rows }) {
  const headers = ['Job Title', 'Company', 'Platform', 'Relevance Score', 'Date Applied', 'Current Status']

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[56rem] text-left text-sm">
        <thead>
          <tr className="border-y border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
            {headers.map((header) => (
              <th key={header} scope="col" className="px-5 py-3 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.id} className="transition-colors hover:bg-slate-50">
              <td className="px-5 py-3.5 font-medium text-slate-900">{row.title}</td>
              <td className="px-5 py-3.5 text-slate-700">{row.company}</td>
              <td className="px-5 py-3.5 text-slate-700">{row.platform}</td>
              <td className="px-5 py-3.5">
                <ScoreBadge score={row.score} />
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-slate-600 tabular-nums">
                {dateFormatter.format(new Date(row.date))}
              </td>
              <td className="px-5 py-3.5">
                <StatusBadge status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-6" aria-hidden="true">
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((key) => (
          <div key={key} className={`${panelClass} h-34`} />
        ))}
      </div>
      <div className={`${panelClass} h-52`} />
      <div className={`${panelClass} h-96`} />
    </div>
  )
}

/* ------------------------------- Main screen ----------------------------- */

export default function AnalyticsDashboard({ onToast }) {
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 1000)
    return () => clearTimeout(timer)
  }, [])

  function handleExport() {
    setExporting(true)
    setTimeout(() => {
      setExporting(false)
      onToast('Application history exported as CSV')
    }, 1200)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Analytics Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Track every application across your connected platforms.
          </p>
        </div>
        <button
          type="button"
          onClick={handleExport}
          disabled={loading || exporting}
          className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {exporting ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Download className="size-4" aria-hidden="true" />
          )}
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

      {loading ? (
        <div role="status">
          <p className="mb-4 flex items-center gap-2 text-sm text-slate-600">
            <LoaderCircle className="size-4 animate-spin text-blue-600" aria-hidden="true" />
            Loading your analytics…
          </p>
          <DashboardSkeleton />
        </div>
      ) : (
        <>
          <section aria-label="Key metrics" className="grid gap-4 sm:grid-cols-3">
            {MOCK_KPIS.map((kpi) => (
              <KpiCard key={kpi.label} {...kpi} />
            ))}
          </section>

          <section className={`${panelClass} p-5`}>
            <h2 className="mb-3 text-base font-semibold text-slate-900">
              Applications by Platform
            </h2>
            <PlatformChart platforms={MOCK_PLATFORMS} />
          </section>

          <section className={panelClass}>
            <h2 className="p-5 text-base font-semibold text-slate-900">
              Recent Application History
            </h2>
            <HistoryTable rows={MOCK_HISTORY} />
          </section>
        </>
      )}
    </div>
  )
}
