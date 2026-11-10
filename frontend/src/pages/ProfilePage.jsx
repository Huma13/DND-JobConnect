import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileUp, Lightbulb, LoaderCircle, Save, UploadCloud } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import TagInput from '../components/TagInput.jsx'

const MAX_BYTES = 5 * 1024 * 1024 // REQ-1
const EMPTY = {
  full_name: '',
  skills: [],
  years_of_experience: 0,
  highest_qualification: '',
  preferred_roles: [],
  preferred_locations: [],
}

const panelClass = 'rounded-xl border border-slate-200 bg-white p-6 shadow-sm'
const inputClass =
  'mt-1.5 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20'
const labelClass = 'block text-sm font-medium text-slate-700'

function ResumeUpload({ onParsed, onToast }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function upload(file) {
    setError('')
    if (!file) return
    if (!/\.(pdf|docx)$/i.test(file.name)) return setError('Only PDF and DOCX files are accepted.')
    if (file.size > MAX_BYTES) return setError('The file is larger than 5 MB. Please upload a smaller file.')
    setBusy(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post('/resume/upload/', form)
      onParsed(data)
      onToast('Resume parsed. Check the details below and save.')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <section className={panelClass}>
      <h2 className="text-base font-semibold text-slate-900">1. Upload your resume</h2>
      <p className="mt-1 text-sm text-slate-600">PDF or DOCX, up to 5 MB. Scanned image-only PDFs can't be read.</p>
      <label
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          upload(e.dataTransfer.files?.[0])
        }}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        {busy ? (
          <LoaderCircle className="size-7 animate-spin text-blue-600" aria-hidden="true" />
        ) : (
          <UploadCloud className="size-7 text-slate-400" aria-hidden="true" />
        )}
        <span className="text-sm font-medium text-slate-800">
          {busy ? 'Reading your resume…' : 'Drop your resume here or click to choose'}
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="sr-only"
          onChange={(e) => upload(e.target.files?.[0])}
          disabled={busy}
        />
      </label>
      {error && (
        <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  )
}

function ProfileTips() {
  const [tips, setTips] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/resume/tips/', {})
      setTips(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={panelClass}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <Lightbulb className="size-4.5 text-amber-500" aria-hidden="true" />
            Profile optimisation tips
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Compares your profile with the postings in your feed and lists what they ask for that you don't mention.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
        >
          {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
          {tips ? 'Refresh tips' : 'Get tips'}
        </button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {tips && (
        <div className="mt-5 space-y-5 text-sm">
          {tips.postings_analyzed > 0 && (
            <p className="text-slate-700">
              <span className="font-semibold tabular-nums text-slate-900">{Math.round(tips.coverage * 100)}%</span> of
              the common keywords in {tips.postings_analyzed} {tips.target_role} postings already appear in your profile.
            </p>
          )}
          {tips.missing_keywords.length > 0 && (
            <div>
              <h3 className="font-medium text-slate-900">Keywords to add if you have them</h3>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {tips.missing_keywords.map((k) => (
                  <li key={k.keyword} className="rounded-md bg-amber-50 px-2 py-1 text-amber-900 ring-1 ring-amber-600/20 ring-inset">
                    {k.keyword} <span className="text-amber-700 tabular-nums">· {k.postings} postings</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {tips.headline_suggestions.length > 0 && (
            <div>
              <h3 className="font-medium text-slate-900">Headline ideas</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">
                {tips.headline_suggestions.map((h) => <li key={h}>{h}</li>)}
              </ul>
            </div>
          )}
          {tips.postings_analyzed === 0 && <p className="text-slate-500">Run a job search first, then come back for tips based on those postings.</p>}
          {tips.postings_analyzed > 0 && tips.notes.map((note) => <p key={note} className="text-slate-500">{note}</p>)}
        </div>
      )}
    </section>
  )
}

export default function ProfilePage({ onToast }) {
  const [profile, setProfile] = useState(null)
  const [exists, setExists] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api
      .get('/resume/profile/')
      .then(({ data }) => {
        if (!active) return
        setProfile(data)
        setExists(true)
      })
      .catch((err) => {
        if (!active) return
        if (err.response?.status === 404) setProfile(EMPTY)
        else setError(errorMessage(err))
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  function update(field, value) {
    setProfile((p) => ({ ...p, [field]: value }))
  }

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const { data } = await api.put('/resume/profile/', {
        ...profile,
        years_of_experience: Number(profile.years_of_experience) || 0,
      })
      setProfile(data)
      onToast('Profile saved. Your feed has been re-ranked.')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Your profile</h1>
        <p className="mt-1 text-sm text-slate-600">
          Matching uses these details to rank jobs. Upload a resume to fill them in, then correct anything that's off.
        </p>
      </div>

      <ResumeUpload
        onToast={onToast}
        onParsed={(data) => {
          setProfile((p) => ({ ...(p || EMPTY), ...data, full_name: data.full_name || p?.full_name || '' }))
          setExists(true)
        }}
      />

      <form onSubmit={save} className={panelClass}>
        <h2 className="text-base font-semibold text-slate-900">2. Review your details</h2>
        {loading ? (
          <p role="status" className="flex items-center gap-2 py-8 text-sm text-slate-600">
            <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
            Loading profile…
          </p>
        ) : !exists ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-slate-600">
            <FileUp className="size-4 text-slate-400" aria-hidden="true" />
            Upload your resume above to create your profile.
          </p>
        ) : (
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <label className={labelClass}>
              Full name
              <input className={inputClass} value={profile.full_name} onChange={(e) => update('full_name', e.target.value)} />
            </label>
            <label className={labelClass}>
              Years of experience
              <input
                type="number"
                min="0"
                max="99"
                className={inputClass}
                value={profile.years_of_experience}
                onChange={(e) => update('years_of_experience', e.target.value)}
              />
            </label>
            <label className={`${labelClass} sm:col-span-2`}>
              Highest qualification
              <input
                className={inputClass}
                value={profile.highest_qualification}
                onChange={(e) => update('highest_qualification', e.target.value)}
              />
            </label>
            <div className="sm:col-span-2">
              <label htmlFor="skills" className={labelClass}>Skills</label>
              <TagInput id="skills" values={profile.skills} onChange={(v) => update('skills', v)} placeholder="Add a skill and press Enter" />
            </div>
            <div>
              <label htmlFor="roles" className={labelClass}>Preferred roles (up to 5)</label>
              <TagInput id="roles" max={5} values={profile.preferred_roles} onChange={(v) => update('preferred_roles', v)} placeholder="e.g. Backend Engineer" />
            </div>
            <div>
              <label htmlFor="locations" className={labelClass}>Preferred locations</label>
              <TagInput id="locations" values={profile.preferred_locations} onChange={(v) => update('preferred_locations', v)} placeholder="e.g. Bengaluru, Remote" />
            </div>
          </div>
        )}
        {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {exists && (
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {saving ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
              Save profile
            </button>
            <Link to="/feed" className="text-sm font-medium text-blue-700 hover:underline">
              Go to job feed →
            </Link>
          </div>
        )}
      </form>

      {exists && <ProfileTips />}
    </div>
  )
}
