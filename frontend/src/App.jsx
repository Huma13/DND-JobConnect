import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import {
  BriefcaseBusiness,
  CircleCheck,
  ClipboardCheck,
  LayoutDashboard,
  UsersRound,
} from 'lucide-react'
import AnalyticsDashboard from './components/AnalyticsDashboard.jsx'
import OutreachPanel from './components/OutreachPanel.jsx'
import ReviewQueue from './components/ReviewQueue.jsx'

const NAV_ITEMS = [
  { to: '/analytics', label: 'Analytics', icon: LayoutDashboard },
  { to: '/review', label: 'Review', icon: ClipboardCheck },
  { to: '/outreach', label: 'Outreach', icon: UsersRound },
]

function navLinkClass({ isActive }) {
  const state = isActive
    ? 'bg-blue-50 text-blue-700'
    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  return `inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-blue-600 sm:flex-none ${state}`
}

function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-blue-600 text-white">
            <BriefcaseBusiness className="size-4.5" aria-hidden="true" />
          </span>
          <span className="font-semibold tracking-tight text-slate-900">DND-JobConnect</span>
        </div>

        <nav aria-label="Main" className="order-last flex w-full gap-1 sm:order-none sm:w-auto">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={navLinkClass}>
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <span
          className="ml-auto flex size-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700"
          aria-label="Signed in as Aarav Sharma"
          role="img"
        >
          AS
        </span>
      </div>
    </header>
  )
}

function Toast({ message }) {
  return (
    <div
      className="fixed right-4 bottom-4 left-4 z-50 flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-lg transition duration-200 starting:translate-y-2 starting:opacity-0 sm:left-auto"
    >
      <CircleCheck className="size-5 shrink-0 text-emerald-600" aria-hidden="true" />
      <p className="text-sm font-medium text-slate-900">{message}</p>
    </div>
  )
}

export default function App() {
  const [toast, setToast] = useState(null)

  const showToast = useCallback((message) => {
    setToast({ id: Date.now(), message })
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(timer)
  }, [toast])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 font-sans text-slate-900 antialiased">
        <Header />
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<Navigate to="/analytics" replace />} />
            <Route path="/analytics" element={<AnalyticsDashboard onToast={showToast} />} />
            <Route path="/review" element={<ReviewQueue onToast={showToast} />} />
            <Route path="/outreach" element={<OutreachPanel onToast={showToast} />} />
          </Routes>
        </main>
        <div aria-live="polite">{toast && <Toast key={toast.id} message={toast.message} />}</div>
      </div>
    </BrowserRouter>
  )
}
