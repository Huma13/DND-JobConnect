import { useCallback, useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'
import { api, listOf } from '../api/client.js'
import { timeAgo } from '../lib/format.js'

const POLL_MS = 60_000

// In-app notifications: CAPTCHA stops (REQ-13) and application status changes.
export default function NotificationBell() {
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const load = useCallback(() => {
    api.get('/applications/notifications/').then(({ data }) => setItems(listOf(data))).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    if (!open) return undefined
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const unread = items.filter((n) => !n.read).length

  async function markRead(note) {
    if (note.read) return
    setItems((all) => all.map((n) => (n.id === note.id ? { ...n, read: true } : n)))
    await api.post(`/applications/notifications/${note.id}/read/`).catch(() => {})
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o)
          if (!open) load()
        }}
        aria-expanded={open}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
      >
        <Bell className="size-5" aria-hidden="true" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white tabular-nums">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          <p className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-900">Notifications</p>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-slate-500">Nothing yet.</p>
          ) : (
            <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
              {items.map((note) => (
                <li key={note.id}>
                  <button
                    type="button"
                    onClick={() => markRead(note)}
                    className={`block w-full px-4 py-3 text-left text-sm hover:bg-slate-50 ${note.read ? 'text-slate-500' : 'text-slate-900'}`}
                  >
                    <span className="flex gap-2">
                      {!note.read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-blue-600" aria-label="Unread" />}
                      <span>{note.message}</span>
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-400">{timeAgo(note.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
