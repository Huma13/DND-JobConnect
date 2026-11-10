import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { BriefcaseBusiness, LoaderCircle } from 'lucide-react'
import { errorMessage } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'

const inputClass =
  'mt-1.5 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20'

export default function LoginPage() {
  const { email, login, register } = useAuth()
  const location = useLocation()
  const [mode, setMode] = useState('login')
  const [address, setAddress] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (email) return <Navigate to={location.state?.from || '/'} replace />

  const isLogin = mode === 'login'

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (isLogin) await login(address.trim(), password)
      else await register(address.trim(), password)
    } catch (err) {
      setError(
        isLogin && err.response?.status === 401
          ? 'Email or password is incorrect.'
          : errorMessage(err),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="flex size-11 items-center justify-center rounded-xl bg-blue-600 text-white">
            <BriefcaseBusiness className="size-5" aria-hidden="true" />
          </span>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">DND-JobConnect</h1>
          <p className="mt-1 text-sm text-slate-600">
            Find matching jobs across LinkedIn, Naukri and X, and apply with your approval.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">{isLogin ? 'Sign in' : 'Create your account'}</h2>

          <label className="block text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className={inputClass}
            />
          </label>

          <label className="block text-sm font-medium text-slate-700">
            Password
            <input
              type="password"
              required
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
            {!isLogin && (
              <span className="mt-1 block text-xs font-normal text-slate-500">
                At least 8 characters, not only numbers, not a common password.
              </span>
            )}
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60"
          >
            {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
            {isLogin ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-600">
          {isLogin ? 'New here?' : 'Already have an account?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode(isLogin ? 'register' : 'login')
              setError('')
            }}
            className="font-medium text-blue-700 hover:underline"
          >
            {isLogin ? 'Create an account' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  )
}
