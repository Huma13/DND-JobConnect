import { useState } from 'react'
import { X } from 'lucide-react'

// Editable list of short values (skills, roles, locations). Enter or comma adds a value.
export default function TagInput({ id, values, onChange, placeholder, max }) {
  const [draft, setDraft] = useState('')
  const full = max != null && values.length >= max

  function add(raw) {
    const value = raw.trim()
    if (!value || full) return
    if (!values.some((v) => v.toLowerCase() === value.toLowerCase())) onChange([...values, value])
    setDraft('')
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      add(draft)
    } else if (event.key === 'Backspace' && !draft && values.length) {
      onChange(values.slice(0, -1))
    }
  }

  return (
    <div className="mt-1.5 flex min-h-10 flex-wrap items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2 py-1.5 shadow-sm focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-600/20">
      {values.map((value) => (
        <span key={value} className="inline-flex items-center gap-1 rounded-md bg-slate-100 py-0.5 pr-1 pl-2 text-sm text-slate-800">
          {value}
          <button
            type="button"
            onClick={() => onChange(values.filter((v) => v !== value))}
            className="rounded p-0.5 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
            aria-label={`Remove ${value}`}
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => add(draft)}
        disabled={full}
        placeholder={full ? `Up to ${max}` : placeholder}
        className="min-w-32 flex-1 border-0 bg-transparent px-1 py-0.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed"
      />
    </div>
  )
}
