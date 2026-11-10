export const PLATFORM_LABELS = {
  linkedin: 'LinkedIn',
  naukri: 'Naukri',
  x: 'X',
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  email: 'Email',
}

export const PLATFORM_BADGES = {
  linkedin: 'bg-sky-50 text-sky-800 ring-sky-600/20',
  naukri: 'bg-indigo-50 text-indigo-800 ring-indigo-600/20',
  x: 'bg-slate-100 text-slate-800 ring-slate-500/20',
  greenhouse: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20',
  lever: 'bg-violet-50 text-violet-800 ring-violet-600/20',
  email: 'bg-amber-50 text-amber-900 ring-amber-600/20',
}

export function platformLabel(platform) {
  return PLATFORM_LABELS[platform] || platform
}

export function scoreClass(score) {
  if (score >= 75) return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
  if (score >= 50) return 'bg-blue-50 text-blue-700 ring-blue-600/20'
  return 'bg-amber-50 text-amber-800 ring-amber-600/20'
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function timeAgo(value) {
  if (!value) return ''
  const days = Math.round((new Date(value).getTime() - Date.now()) / 86_400_000)
  if (days === 0) {
    const hours = Math.round((new Date(value).getTime() - Date.now()) / 3_600_000)
    return hours === 0 ? 'just now' : relative.format(hours, 'hour')
  }
  return relative.format(days, 'day')
}

const dateFormatter = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

export function formatDate(value) {
  return value ? dateFormatter.format(new Date(value)) : ''
}

// Career-page apply (Greenhouse/Lever) is possible only for postings hosted there.
export function atsFor(url) {
  try {
    const host = new URL(url).hostname
    if (host.endsWith('greenhouse.io')) return 'greenhouse'
    if (host.endsWith('lever.co')) return 'lever'
  } catch {
    // not a URL
  }
  return null
}
