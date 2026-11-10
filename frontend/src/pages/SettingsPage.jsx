import { useEffect, useState } from 'react'
import { CirclePause, CirclePlay, LoaderCircle } from 'lucide-react'
import { api, errorMessage, listOf } from '../api/client.js'
import { formatDate, platformLabel } from '../lib/format.js'

const panelClass = 'rounded-xl border border-slate-200 bg-white p-6 shadow-sm'
const inputClass =
  'mt-1.5 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20'
const buttonClass =
  'inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60'
const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function Section({ title, description, children }) {
  return (
    <section className={panelClass}>
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      <div className="mt-5">{children}</div>
    </section>
  )
}

function useSave(onToast) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function run(action, message) {
    setBusy(true)
    setError('')
    try {
      const result = await action()
      if (message) onToast(message)
      return result
    } catch (err) {
      setError(errorMessage(err))
      return null
    } finally {
      setBusy(false)
    }
  }
  const alert = error && <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
  return { busy, run, alert }
}

// SRS 6.2: one switch that stops every scheduled and in-flight automation.
function PauseAll({ onToast }) {
  const [paused, setPaused] = useState(null)
  const { busy, run, alert } = useSave(onToast)
  useEffect(() => {
    api.get('/auth/pause/').then(({ data }) => setPaused(data.automation_paused)).catch(() => {})
  }, [])
  async function toggle() {
    const data = await run(async () => (await api.post('/auth/pause/', { paused: !paused })).data,
      paused ? 'Automation resumed' : 'All automation paused')
    if (data) setPaused(data.automation_paused)
  }
  if (paused === null) return null
  return (
    <section className={`${panelClass} flex flex-wrap items-center justify-between gap-4 ${paused ? 'border-amber-300 bg-amber-50' : ''}`}>
      <div>
        <h2 className="text-base font-semibold text-slate-900">{paused ? 'Automation is paused' : 'Automation is running'}</h2>
        <p className="mt-1 text-sm text-slate-600">
          {paused
            ? 'No searches, submissions or messages will run until you resume.'
            : 'Pause stops scheduled searches, submissions and outreach immediately.'}
        </p>
        {alert}
      </div>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold ${
          paused ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-amber-500 text-amber-950 hover:bg-amber-400'
        }`}
      >
        {paused ? <CirclePlay className="size-4" aria-hidden="true" /> : <CirclePause className="size-4" aria-hidden="true" />}
        {paused ? 'Resume automation' : 'Pause all automation'}
      </button>
    </section>
  )
}

function Platforms({ onToast }) {
  const [platforms, setPlatforms] = useState(null)
  const { busy, run, alert } = useSave(onToast)
  useEffect(() => {
    api.get('/jobs/preferences/').then(({ data }) => setPlatforms(data.platforms)).catch(() => {})
  }, [])
  if (!platforms) return null
  return (
    <Section title="Job sources" description="Which platforms searches use (REQ-5).">
      <div className="flex flex-wrap gap-4">
        {['linkedin', 'naukri', 'x'].map((p) => (
          <label key={p} className="flex items-center gap-2 text-sm text-slate-800">
            <input
              type="checkbox"
              className="size-4 rounded border-slate-300 text-blue-600"
              checked={platforms.includes(p)}
              onChange={(e) => setPlatforms(e.target.checked ? [...platforms, p] : platforms.filter((x) => x !== p))}
            />
            {platformLabel(p)}
          </label>
        ))}
      </div>
      <button
        type="button"
        disabled={busy || platforms.length === 0}
        onClick={() => run(() => api.put('/jobs/preferences/', { platforms }), 'Job sources saved')}
        className={`${buttonClass} mt-5`}
      >
        Save sources
      </button>
      {alert}
    </Section>
  )
}

function Schedule({ onToast }) {
  const [schedule, setSchedule] = useState(null)
  const [exists, setExists] = useState(false)
  const { busy, run, alert } = useSave(onToast)
  useEffect(() => {
    api
      .get('/scheduler/schedule/')
      .then(({ data }) => {
        setSchedule({ ...data, run_time: data.run_time.slice(0, 5) })
        setExists(true)
      })
      .catch(() =>
        setSchedule({ cadence: 'daily', run_time: '09:00', weekday: 0, enabled: true,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata' }),
      )
  }, [])
  if (!schedule) return null
  const set = (patch) => setSchedule((s) => ({ ...s, ...patch }))
  async function save() {
    const body = { ...schedule, weekday: schedule.cadence === 'weekly' ? Number(schedule.weekday) : null }
    if (await run(() => api.put('/scheduler/schedule/', body), 'Schedule saved')) setExists(true)
  }
  async function remove() {
    if (await run(() => api.delete('/scheduler/schedule/'), 'Schedule removed')) setExists(false)
  }
  return (
    <Section title="Scheduled searches" description={`Run a search automatically (REQ-18). Times are in ${schedule.timezone}.`}>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block text-sm font-medium text-slate-700">
          How often
          <select className={inputClass} value={schedule.cadence} onChange={(e) => set({ cadence: e.target.value })}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </label>
        {schedule.cadence === 'weekly' && (
          <label className="block text-sm font-medium text-slate-700">
            Day
            <select className={inputClass} value={schedule.weekday ?? 0} onChange={(e) => set({ weekday: e.target.value })}>
              {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </label>
        )}
        <label className="block text-sm font-medium text-slate-700">
          Time
          <input type="time" className={inputClass} value={schedule.run_time} onChange={(e) => set({ run_time: e.target.value })} />
        </label>
      </div>
      <label className="mt-4 flex items-center gap-2 text-sm text-slate-800">
        <input type="checkbox" className="size-4 rounded border-slate-300 text-blue-600" checked={schedule.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
        Enabled
      </label>
      <div className="mt-5 flex gap-3">
        <button type="button" onClick={save} disabled={busy} className={buttonClass}>Save schedule</button>
        {exists && (
          <button type="button" onClick={remove} disabled={busy} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Remove
          </button>
        )}
      </div>
      {alert}
    </Section>
  )
}

function Limits({ onToast }) {
  const [apply, setApply] = useState(null)
  const [outreach, setOutreach] = useState(null)
  const { run, alert } = useSave(onToast)
  useEffect(() => {
    api.get('/applications/limits/').then(({ data }) => setApply(data)).catch(() => {})
    api.get('/outreach/limits/').then(({ data }) => setOutreach(data)).catch(() => {})
  }, [])
  async function updateApply(platform, patch) {
    const data = await run(async () => (await api.put('/applications/limits/', { platform, ...patch })).data, 'Saved')
    if (data) setApply(data)
  }
  async function updateOutreach(platform, daily_limit) {
    const data = await run(async () => (await api.put('/outreach/limits/', { platform, daily_limit })).data, 'Saved')
    if (data) setOutreach(data)
  }
  if (!apply || !outreach) return null
  return (
    <Section
      title="Daily limits and Full-Auto"
      description="Caps keep your accounts safe (REQ-11, REQ-16). Full-Auto skips the review step for that channel (REQ-10)."
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs text-slate-600">
              <th className="py-2 font-medium">Applications via</th>
              <th className="py-2 font-medium">Used today</th>
              <th className="py-2 font-medium">Daily limit</th>
              <th className="py-2 font-medium">Full-Auto</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {apply.map((row) => (
              <tr key={row.platform}>
                <td className="py-2.5 text-slate-900">{platformLabel(row.platform)}</td>
                <td className="py-2.5 tabular-nums text-slate-700">{row.used_today}</td>
                <td className="py-2.5">
                  <input
                    type="number"
                    min="0"
                    max="500"
                    defaultValue={row.daily_limit}
                    onBlur={(e) => Number(e.target.value) !== row.daily_limit && updateApply(row.platform, { daily_limit: Number(e.target.value) })}
                    className="w-20 rounded-md border border-slate-300 px-2 py-1 text-sm tabular-nums"
                    aria-label={`Daily application limit for ${platformLabel(row.platform)}`}
                  />
                </td>
                <td className="py-2.5">
                  {['linkedin', 'naukri'].includes(row.platform) ? (
                    <span className="text-xs text-slate-500">You apply on the site</span>
                  ) : (
                    <input
                      type="checkbox"
                      checked={row.full_auto}
                      onChange={(e) => updateApply(row.platform, { full_auto: e.target.checked })}
                      className="size-4 rounded border-slate-300 text-blue-600"
                      aria-label={`Full-Auto for ${platformLabel(row.platform)}`}
                    />
                  )}
                </td>
              </tr>
            ))}
            {outreach.map((row) => (
              <tr key={`o-${row.platform}`}>
                <td className="py-2.5 text-slate-900">{platformLabel(row.platform)} outreach</td>
                <td className="py-2.5 tabular-nums text-slate-700">{row.sent_today}</td>
                <td className="py-2.5">
                  <input
                    type="number"
                    min="0"
                    max="200"
                    defaultValue={row.daily_limit}
                    onBlur={(e) => Number(e.target.value) !== row.daily_limit && updateOutreach(row.platform, Number(e.target.value))}
                    className="w-20 rounded-md border border-slate-300 px-2 py-1 text-sm tabular-nums"
                    aria-label={`Daily outreach limit for ${platformLabel(row.platform)}`}
                  />
                </td>
                <td />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {alert}
    </Section>
  )
}

function Mailbox({ onToast }) {
  const [box, setBox] = useState(null)
  const [exists, setExists] = useState(false)
  const { busy, run, alert } = useSave(onToast)
  useEffect(() => {
    api
      .get('/applications/mailbox/')
      .then(({ data }) => {
        setBox({ ...data, password: '' })
        setExists(true)
      })
      .catch(() => setBox({ host: 'smtp.gmail.com', port: 587, username: '', password: '', from_email: '', use_tls: true }))
  }, [])
  if (!box) return null
  const set = (patch) => setBox((b) => ({ ...b, ...patch }))
  async function save(e) {
    e.preventDefault()
    const body = { ...box, port: Number(box.port) }
    if (exists && !body.password) delete body.password
    const method = exists && !body.password ? 'patch' : 'put'
    if (await run(() => api[method]('/applications/mailbox/', body), 'Mailbox saved')) {
      setExists(true)
      set({ password: '' })
    }
  }
  return (
    <Section title="Your mailbox" description="Email applications are sent from your own account. The password is stored encrypted and never shown again.">
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-medium text-slate-700">SMTP host<input required className={inputClass} value={box.host} onChange={(e) => set({ host: e.target.value })} /></label>
        <label className="block text-sm font-medium text-slate-700">Port<input required type="number" className={inputClass} value={box.port} onChange={(e) => set({ port: e.target.value })} /></label>
        <label className="block text-sm font-medium text-slate-700">Username<input className={inputClass} value={box.username} onChange={(e) => set({ username: e.target.value })} /></label>
        <label className="block text-sm font-medium text-slate-700">
          Password {exists && <span className="font-normal text-slate-500">(leave blank to keep)</span>}
          <input type="password" required={!exists} className={inputClass} value={box.password} onChange={(e) => set({ password: e.target.value })} autoComplete="new-password" />
        </label>
        <label className="block text-sm font-medium text-slate-700">From address<input required type="email" className={inputClass} value={box.from_email} onChange={(e) => set({ from_email: e.target.value })} /></label>
        <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-800">
          <input type="checkbox" className="size-4 rounded border-slate-300 text-blue-600" checked={box.use_tls} onChange={(e) => set({ use_tls: e.target.checked })} />
          Use TLS
        </label>
        <div className="sm:col-span-2">
          <button type="submit" disabled={busy} className={buttonClass}>{busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}Save mailbox</button>
          {alert}
        </div>
      </form>
    </Section>
  )
}

function RunLog() {
  const [runs, setRuns] = useState(null)
  const [usage, setUsage] = useState([])
  useEffect(() => {
    api.get('/scheduler/runs/').then(({ data }) => setRuns(listOf(data).slice(0, 10))).catch(() => setRuns([]))
    api.get('/scheduler/rate-limits/').then(({ data }) => setUsage(data)).catch(() => {})
  }, [])
  return (
    <Section title="Search runs and rate limits" description="Each run's results (REQ-20). Actions are held back at 90% of a platform's limit (REQ-19).">
      <div className="mb-5 flex flex-wrap gap-3">
        {usage.map((u) => (
          <div key={`${u.platform}-${u.action}`} className="min-w-40 rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <p className="font-medium text-slate-900">{platformLabel(u.platform)} {u.action}</p>
            <p className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <span className={`block h-full rounded-full ${u.held ? 'bg-amber-500' : 'bg-blue-600'}`} style={{ width: `${Math.min(100, (u.used / u.limit) * 100)}%` }} />
            </p>
            <p className="mt-1 text-xs tabular-nums text-slate-600">{u.used} of {u.limit} · held at {u.hold_at}</p>
          </div>
        ))}
      </div>
      {!runs ? null : runs.length === 0 ? (
        <p className="text-sm text-slate-500">No runs yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs text-slate-600">
                <th className="py-2 font-medium">Started</th>
                <th className="py-2 font-medium">Trigger</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 text-right font-medium">Found</th>
                <th className="py-2 text-right font-medium">New</th>
                <th className="py-2 text-right font-medium">Merged</th>
                <th className="py-2 pl-4 font-medium">Problems</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="py-2 whitespace-nowrap text-slate-700">{formatDate(r.started_at)} {new Date(r.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                  <td className="py-2 capitalize text-slate-700">{r.trigger}</td>
                  <td className="py-2 capitalize text-slate-700">{r.status}</td>
                  <td className="py-2 text-right tabular-nums">{r.postings_found}</td>
                  <td className="py-2 text-right tabular-nums">{r.new_matches}</td>
                  <td className="py-2 text-right tabular-nums">{r.duplicates_hidden}</td>
                  <td className="py-2 pl-4 text-xs text-amber-800">{(r.errors || []).map((e) => `${platformLabel(e.platform)}: ${e.error}`).join('; ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

export default function SettingsPage({ onToast }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-600">Control what runs automatically and how much.</p>
      </div>
      <PauseAll onToast={onToast} />
      <Platforms onToast={onToast} />
      <Schedule onToast={onToast} />
      <Limits onToast={onToast} />
      <Mailbox onToast={onToast} />
      <RunLog />
    </div>
  )
}
