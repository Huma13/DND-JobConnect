import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Copy, LoaderCircle, MapPin, Search, Send, UsersRound, X } from 'lucide-react'
import { api, errorMessage, listOf } from '../api/client.js'
import { PLATFORM_BADGES, platformLabel, scoreClass, timeAgo } from '../lib/format.js'
import ApplyDialog from '../components/ApplyDialog.jsx'

const PLATFORMS = ['linkedin', 'naukri', 'x']
const RECENCY = [
  { value: '', label: 'Any time' },
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
]
const DEFAULT_FILTERS = { platforms: [], location: '', minScore: 0, recency: '' }

function buildParams(filters) {
  const params = new URLSearchParams()
  filters.platforms.forEach((p) => params.append('platform', p))
  if (filters.location.trim()) params.set('location', filters.location.trim())
  if (filters.minScore > 0) params.set('min_score', String(filters.minScore))
  if (filters.recency) params.set('posted_within_days', filters.recency)
  return params
}

function FilterRail({ filters, onChange }) {
  const set = (patch) => onChange({ ...filters, ...patch })
  return (
    <aside className="space-y-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:sticky lg:top-24">
      <fieldset>
        <legend className="text-sm font-semibold text-slate-900">Platform</legend>
        <div className="mt-2 space-y-1.5">
          {PLATFORMS.map((p) => (
            <label key={p} className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="size-4 rounded border-slate-300 text-blue-600"
                checked={filters.platforms.includes(p)}
                onChange={(e) =>
                  set({ platforms: e.target.checked ? [...filters.platforms, p] : filters.platforms.filter((x) => x !== p) })
                }
              />
              {platformLabel(p)}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="block text-sm font-semibold text-slate-900">
        Location
        <input
          value={filters.location}
          onChange={(e) => set({ location: e.target.value })}
          placeholder="e.g. Bengaluru"
          className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-normal focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
        />
      </label>
      <label className="block text-sm font-semibold text-slate-900">
        Minimum relevance <span className="font-normal tabular-nums text-slate-500">{filters.minScore}</span>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={filters.minScore}
          onChange={(e) => set({ minScore: Number(e.target.value) })}
          className="mt-2 w-full accent-blue-600"
        />
      </label>
      <label className="block text-sm font-semibold text-slate-900">
        Posted
        <select
          value={filters.recency}
          onChange={(e) => set({ recency: e.target.value })}
          className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-normal"
        >
          {RECENCY.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={() => onChange(DEFAULT_FILTERS)}
        className="text-sm font-medium text-blue-700 hover:underline"
      >
        Clear filters
      </button>
    </aside>
  )
}

function JobRow({ item, onApply, onSkip }) {
  return (
    <li className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-slate-900 hover:text-blue-700 hover:underline"
          >
            {item.title}
          </a>
          <span className={`rounded-md px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ${PLATFORM_BADGES[item.platform]}`}>
            {platformLabel(item.platform)}
          </span>
          {item.also_on.length > 0 && (
            <span
              className="inline-flex items-center gap-1 rounded-md bg-slate-50 px-1.5 py-0.5 text-xs text-slate-600 ring-1 ring-slate-200 ring-inset"
              title="The same job was found on other platforms and merged into this row (REQ-7)"
            >
              <Copy className="size-3" aria-hidden="true" />
              Also on {[...new Set(item.also_on.map((a) => platformLabel(a.platform)))].join(', ')}
            </span>
          )}
          {item.state === 'applied' && (
            <span className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-700">Applied</span>
          )}
        </div>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-slate-600">
          {item.company}
          {item.location && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3.5" aria-hidden="true" />
                {item.location}
              </span>
            </>
          )}
          {item.posted_at && (
            <>
              <span aria-hidden="true">·</span>
              {timeAgo(item.posted_at)}
            </>
          )}
        </p>
      </div>

      <div className="flex w-28 shrink-0 flex-col gap-1" aria-label={`Relevance ${item.relevance} out of 100`}>
        <span className={`self-start rounded-md px-2 py-0.5 text-sm font-semibold tabular-nums ring-1 ring-inset ${scoreClass(item.relevance)}`}>
          {item.relevance}
        </span>
        <span className="h-1 w-full overflow-hidden rounded-full bg-slate-100">
          <span className="block h-full rounded-full bg-blue-600" style={{ width: `${item.relevance}%` }} />
        </span>
      </div>

      <div className="flex shrink-0 flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onApply(item)}
          disabled={item.state === 'applied'}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-500"
        >
          <Send className="size-3.5" aria-hidden="true" />
          Apply
        </button>
        <Link
          to={`/outreach?feed_item=${item.id}`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <UsersRound className="size-3.5" aria-hidden="true" />
          Recruiters
        </Link>
        <button
          type="button"
          onClick={() => onSkip(item)}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          aria-label={`Skip ${item.title}`}
        >
          <X className="size-4" aria-hidden="true" />
          Skip
        </button>
      </div>
    </li>
  )
}

export default function FeedPage({ onToast }) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [items, setItems] = useState(null)
  const [next, setNext] = useState(null)
  const [count, setCount] = useState(0)
  const [error, setError] = useState('')
  const [searching, setSearching] = useState(false)
  const [lastRun, setLastRun] = useState(null)
  const [applying, setApplying] = useState(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    const timer = setTimeout(() => {
      api
        .get(`/jobs/feed/?${buildParams(filters)}`)
        .then(({ data }) => {
          if (!active) return
          setItems(listOf(data))
          setNext(data.next)
          setCount(data.count ?? listOf(data).length)
          setError('')
        })
        .catch((err) => active && setError(errorMessage(err)))
    }, 250)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [filters, reload])

  async function loadMore() {
    try {
      const { data } = await api.get(next)
      setItems((current) => [...current, ...listOf(data)])
      setNext(data.next)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const pollRun = useCallback(async (runId) => {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const { data } = await api.get(`/scheduler/runs/${runId}/`)
      if (data.status !== 'running') return data
      await new Promise((resolve) => setTimeout(resolve, 1500))
    }
    return null
  }, [])

  async function searchNow() {
    setSearching(true)
    setError('')
    try {
      const { data } = await api.post('/jobs/feed/search/')
      const run = await pollRun(data.run_id)
      setLastRun(run)
      setReload((n) => n + 1)
      if (run) onToast(`Search finished: ${run.new_matches} new matches, ${run.duplicates_hidden} duplicates merged.`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSearching(false)
    }
  }

  async function skip(item) {
    setItems((current) => current.filter((i) => i.id !== item.id))
    setCount((c) => c - 1)
    try {
      await api.post(`/jobs/feed/${item.id}/skip/`)
    } catch (err) {
      setError(errorMessage(err))
      setReload((n) => n + 1)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Job feed</h1>
          <p className="mt-1 text-sm text-slate-600">
            Ranked by how well each posting matches your profile. Duplicates across platforms are merged.
          </p>
        </div>
        <button
          type="button"
          onClick={searchNow}
          disabled={searching}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {searching ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Search className="size-4" aria-hidden="true" />}
          {searching ? 'Searching…' : 'Search now'}
        </button>
      </div>

      {lastRun && (
        <p className="rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-700">
          Last search: {lastRun.postings_found} postings found on {lastRun.platforms.map(platformLabel).join(', ') || 'no platforms'},{' '}
          {lastRun.new_matches} new, {lastRun.duplicates_hidden} duplicates merged
          {lastRun.errors?.length > 0 && <span className="text-amber-700"> · {lastRun.errors.map((e) => `${platformLabel(e.platform)}: ${e.error}`).join('; ')}</span>}
        </p>
      )}
      {error && <p role="alert" className="rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <FilterRail filters={filters} onChange={setFilters} />

        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-3 text-sm text-slate-600">
            <span className="font-semibold tabular-nums text-slate-900">{count}</span> matching jobs
          </div>
          {items === null ? (
            <p role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-slate-600">
              <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
              Loading your feed…
            </p>
          ) : items.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-slate-600">
              <p className="font-medium text-slate-900">No jobs here yet</p>
              <p className="mt-1">
                Check your <Link to="/profile" className="text-blue-700 hover:underline">profile</Link> has a preferred role,
                then press <span className="font-medium">Search now</span>, or loosen the filters.
              </p>
            </div>
          ) : (
            <>
              <ul className="divide-y divide-slate-100">
                {items.map((item) => (
                  <JobRow key={item.id} item={item} onApply={setApplying} onSkip={skip} />
                ))}
              </ul>
              {next && (
                <div className="border-t border-slate-100 p-4 text-center">
                  <button type="button" onClick={loadMore} className="text-sm font-medium text-blue-700 hover:underline">
                    Load more
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {applying && (
        <ApplyDialog
          item={applying}
          onClose={() => setApplying(null)}
          onDone={(message) => {
            setApplying(null)
            setReload((n) => n + 1)
            if (message) onToast(message)
          }}
        />
      )}
    </div>
  )
}
