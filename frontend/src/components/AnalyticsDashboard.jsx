import { useCallback, useEffect, useState } from 'react'
import {
  CalendarCheck,
  CircleCheck,
  Download,
  FileText,
  LoaderCircle,
  MessageSquareReply,
  Send,
  TriangleAlert,
  XCircle,
  PencilLine,
} from 'lucide-react'
import { api, errorMessage, listOf } from '../api/client.js'
import { formatDate, platformLabel } from '../lib/format.js'

/* --------------------------------- Styles -------------------------------- */

const STATUS_STYLES = {
  draft: { label: 'Draft', className: 'bg-slate-100 text-slate-700', icon: PencilLine },
  applied: { label: 'Applied', className: 'bg-blue-50 text-blue-700', icon: Send },
  submitted: { label: 'Submitted', className: 'bg-emerald-50 text-emerald-700', icon: CircleCheck },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700', icon: XCircle },
  manual_review_required: { label: 'Manual Review Required', className: 'bg-amber-50 text-amber-800', icon: TriangleAlert },
}

const RANGES = [
  { days: 7, label: 'Last 7 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 90, label: 'Last 90 days' },
]

const METHOD_LABELS = { manual: 'Assisted', ats: 'Career page', email: 'Email' }

const panelClass = 'rounded-xl border border-slate-200 bg-white shadow-sm'

function isoDate(date) {
  return date.toISOString().slice(0, 10)
}

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
  if (platforms.length === 0) {
    return <p className="px-2 py-4 text-sm text-slate-500">No applications in this period.</p>
  }
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
            className="group grid grid-cols-[6rem_1fr_2rem] items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-slate-50 sm:grid-cols-[7rem_1fr_2.5rem]"
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

function KeywordTable({ keywords }) {
  const used = keywords.filter((k) => k.application_count > 0)
  if (used.length === 0) {
    return <p className="px-5 pb-5 text-sm text-slate-500">Apply to a few jobs that list your skills to see which ones get replies.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <thead>
          <tr className="border-y border-slate-200 bg-slate-50 text-xs text-slate-600">
            <th scope="col" className="px-5 py-3 font-medium">Resume keyword</th>
            <th scope="col" className="px-5 py-3 text-right font-medium">Applications</th>
            <th scope="col" className="px-5 py-3 text-right font-medium">Responses</th>
            <th scope="col" className="px-5 py-3 font-medium">Response rate</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {used.map((k) => (
            <tr key={k.keyword}>
              <td className="px-5 py-3 font-medium text-slate-900">{k.keyword}</td>
              <td className="px-5 py-3 text-right text-slate-700 tabular-nums">{k.application_count}</td>
              <td className="px-5 py-3 text-right text-slate-700 tabular-nums">{k.response_count}</td>
              <td className="px-5 py-3">
                <span className="flex items-center gap-2">
                  <span className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
                    <span className="block h-full rounded-full bg-emerald-600" style={{ width: `${k.response_rate}%` }} />
                  </span>
                  <span className="text-slate-700 tabular-nums">{k.response_rate}%</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StatusSelect({ app, onChanged, onError }) {
  const style = STATUS_STYLES[app.status] || STATUS_STYLES.draft
  const Icon = style.icon
  return (
    <label className={`inline-flex items-center gap-1.5 rounded-full py-1 pr-1 pl-2.5 text-xs font-medium whitespace-nowrap ${style.className}`}>
      <Icon className="size-3.5" aria-hidden="true" />
      <span className="sr-only">Status of {app.title}</span>
      <select
        value={app.status}
        onChange={async (e) => {
          try {
            const { data } = await api.patch(`/applications/${app.id}/change-status/`, { status: e.target.value })
            onChanged(data)
          } catch (err) {
            onError(errorMessage(err))
          }
        }}
        className="cursor-pointer appearance-none bg-transparent pr-1 font-medium focus:outline-none"
      >
        {Object.entries(STATUS_STYLES).map(([value, { label }]) => (
          <option key={value} value={value}>{label}</option>
        ))}
      </select>
    </label>
  )
}

function HistoryTable({ rows, onChanged, onResponse, onError }) {
  const headers = ['Job Title', 'Company', 'Platform', 'How', 'Date Applied', 'Current Status', 'Employer response']

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[64rem] text-left text-sm">
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
              <td className="px-5 py-3.5 text-slate-700">{platformLabel(row.platform)}</td>
              <td className="px-5 py-3.5 text-slate-700">{METHOD_LABELS[row.method] || row.method}</td>
              <td className="px-5 py-3.5 whitespace-nowrap text-slate-600 tabular-nums">{formatDate(row.created_at)}</td>
              <td className="px-5 py-3.5">
                <StatusSelect app={row} onChanged={onChanged} onError={onError} />
              </td>
              <td className="px-5 py-3.5">
                {['applied', 'submitted'].includes(row.status) && (
                  <span className="flex gap-1.5 whitespace-nowrap">
                    <button type="button" onClick={() => onResponse(row, 'reply')} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">
                      + Reply
                    </button>
                    <button type="button" onClick={() => onResponse(row, 'interview')} className="rounded-md border border-emerald-600/40 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50">
                      + Interview
                    </button>
                  </span>
                )}
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
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    const end = new Date()
    const start = new Date(Date.now() - days * 86_400_000)
    Promise.all([
      api.get(`/applications/statistics/?start_date=${isoDate(start)}&end_date=${isoDate(end)}`),
      api.get('/applications/response-analytics/'),
      api.get('/applications/keyword-analytics/'),
      api.get('/applications/'),
    ])
      .then(([stats, responses, keywords, history]) => {
        if (!active) return
        setData({
          stats: stats.data,
          responses: responses.data,
          keywords: keywords.data.keywords,
          history: listOf(history.data),
        })
        setError('')
      })
      .catch((err) => active && setError(errorMessage(err)))
    return () => {
      active = false
    }
  }, [days, reload])

  const refresh = useCallback(() => setReload((n) => n + 1), [])

  async function handleExport() {
    setExporting(true)
    try {
      const { data: blob } = await api.get('/applications/export/', { responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'application_history.csv'
      link.click()
      URL.revokeObjectURL(url)
      onToast('Application history exported as CSV')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setExporting(false)
    }
  }

  async function logResponse(app, type) {
    try {
      await api.post(`/applications/${app.id}/responses/`, { response_type: type })
      onToast(type === 'interview' ? `Interview logged for ${app.company}` : `Reply logged for ${app.company}`)
      refresh()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const submittedCount = data?.stats.by_status
    .filter((s) => ['applied', 'submitted'].includes(s.status))
    .reduce((sum, s) => sum + s.count, 0)

  const kpis = data && [
    {
      label: 'Total Applications',
      value: data.stats.total_applications,
      caption: `${submittedCount} sent, across ${data.stats.by_platform.length} channels`,
      icon: FileText,
    },
    {
      label: 'Employer Responses',
      value: data.responses.response_count,
      caption: 'Replies and interview invitations',
      icon: CalendarCheck,
    },
    {
      label: 'Response Rate (%)',
      value: `${data.responses.response_rate}%`,
      caption: 'Responses ÷ sent applications',
      icon: MessageSquareReply,
    },
  ]

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
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            aria-label="Date range"
            className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm"
          >
            {RANGES.map((r) => (
              <option key={r.days} value={r.days}>{r.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleExport}
            disabled={!data || exporting}
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
      </div>

      {error && <p role="alert" className="rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700">{error}</p>}

      {!data ? (
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
            {kpis.map((kpi) => (
              <KpiCard key={kpi.label} {...kpi} />
            ))}
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className={`${panelClass} p-5`}>
              <h2 className="mb-3 text-base font-semibold text-slate-900">
                Applications by Channel
              </h2>
              <PlatformChart
                platforms={data.stats.by_platform.map((p) => ({ name: platformLabel(p.platform), count: p.count }))}
              />
            </section>
            <section className={`${panelClass} p-5`}>
              <h2 className="mb-3 text-base font-semibold text-slate-900">
                Responses by Channel
              </h2>
              <PlatformChart
                platforms={data.responses.by_platform
                  .filter((p) => p.response_count > 0)
                  .map((p) => ({ name: platformLabel(p.platform), count: p.response_count }))}
              />
            </section>
          </div>

          <section className={panelClass}>
            <h2 className="p-5 pb-3 text-base font-semibold text-slate-900">Which resume keywords get responses</h2>
            <KeywordTable keywords={data.keywords} />
          </section>

          <section className={panelClass}>
            <h2 className="p-5 text-base font-semibold text-slate-900">
              Recent Application History
            </h2>
            {data.history.length === 0 ? (
              <p className="px-5 pb-5 text-sm text-slate-500">No applications yet.</p>
            ) : (
              <HistoryTable
                rows={data.history}
                onChanged={(updated) => {
                  onToast(`Status updated: ${updated.title}`)
                  refresh()
                }}
                onResponse={logResponse}
                onError={setError}
              />
            )}
          </section>
        </>
      )}
    </div>
  )
}
