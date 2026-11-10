import { useEffect, useState } from 'react'
import { LoaderCircle, ShieldCheck } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'

// SRS section 7: users accept the legal disclaimer before any automation runs.
export default function DisclaimerGate({ children }) {
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api
      .get('/auth/disclaimer/')
      .then(({ data }) => active && setState(data))
      .catch((err) => active && setError(errorMessage(err)))
    return () => {
      active = false
    }
  }, [])

  async function accept() {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/auth/disclaimer/', { accept: true })
      setState(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (state && (state.accepted || !state.required)) return children

  return (
    <div className="mx-auto max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      {!state && !error ? (
        <p role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-slate-600">
          <LoaderCircle className="size-5 animate-spin text-blue-600" aria-hidden="true" />
          Loading…
        </p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
              <ShieldCheck className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h1 className="text-lg font-semibold text-slate-900">Before you start</h1>
              {state && <p className="text-sm text-slate-500">Disclaimer version {state.version}</p>}
            </div>
          </div>
          {state && <p className="mt-4 text-sm leading-6 text-slate-700">{state.text}</p>}
          {error && (
            <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
          {state && (
            <button
              type="button"
              onClick={accept}
              disabled={busy}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
              I understand and accept
            </button>
          )}
        </>
      )}
    </div>
  )
}
