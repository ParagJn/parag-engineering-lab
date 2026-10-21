import { useEffect, useRef, useState } from 'react'
import { Check, FileText, FileImage, Pencil, Plus, Search, Trash2, X } from 'lucide-react'

function when(iso) {
  const date = new Date(iso)
  const sameDay = date.toDateString() === new Date().toDateString()
  return sameDay
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function Item({ item, active, onOpen, onRename, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [title, setTitle] = useState(item.title)
  const Icon = item.type_a === 'image-markdown' || item.type_b === 'image-markdown' ? FileImage : FileText
  const score = Math.round(item.section_similarity * 100)
  const tone = score >= 80 ? 'text-emerald-700' : score >= 50 ? 'text-amber-700' : 'text-red-700'

  function commit() {
    const next = title.trim()
    setEditing(false)
    if (next && next !== item.title) onRename(item.id, next)
    else setTitle(item.title)
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1 rounded-lg border border-slate-900 bg-white p-2">
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit()
            if (e.key === 'Escape') {
              setEditing(false)
              setTitle(item.title)
            }
          }}
          className="min-w-0 flex-1 bg-transparent text-sm font-semibold outline-none"
        />
        <button onClick={commit} className="text-emerald-600" title="Save"><Check size={15} /></button>
      </div>
    )
  }

  return (
    <div
      className={`group relative rounded-lg border p-3 transition ${
        active ? 'border-slate-900 bg-white shadow-sm' : 'border-transparent hover:border-slate-200 hover:bg-white'
      }`}
    >
      <button onClick={() => onOpen(item.id)} className="block w-full text-left">
        <span className="flex items-start gap-2">
          <Icon size={15} className="mt-0.5 shrink-0 text-slate-400" />
          <span className="min-w-0 flex-1">
            <span className="block break-words pr-12 text-sm font-semibold leading-5 text-slate-900">{item.title}</span>
            <span className="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span>{when(item.created_at)}</span>
              <span className={`font-bold ${tone}`}>{score}% similar</span>
            </span>
          </span>
        </span>
      </button>
      <div className={`absolute right-2 top-2 flex items-center gap-1 ${confirming ? '' : 'opacity-0 transition group-hover:opacity-100'}`}>
        {confirming ? (
          <>
            <button onClick={() => onDelete(item.id)} className="rounded bg-red-600 px-2 py-0.5 text-xs font-bold text-white">Delete</button>
            <button onClick={() => setConfirming(false)} className="text-slate-500" title="Cancel"><X size={14} /></button>
          </>
        ) : (
          <>
            <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-slate-900" title="Rename"><Pencil size={14} /></button>
            <button onClick={() => setConfirming(true)} className="text-slate-400 hover:text-red-600" title="Delete"><Trash2 size={14} /></button>
          </>
        )}
      </div>
    </div>
  )
}

export default function HistorySidebar({ items, activeId, loading, error, query, onQuery, onOpen, onNew, onRename, onDelete }) {
  const [text, setText] = useState(query)
  const timer = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])

  function change(value) {
    setText(value)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => onQuery(value), 250)
  }

  return (
    <aside className="flex h-full min-h-0 flex-col gap-3">
      <button
        onClick={onNew}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800"
      >
        <Plus size={16} />
        New comparison
      </button>
      <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
        <Search size={15} className="text-slate-400" />
        <input
          value={text}
          onChange={(e) => change(e.target.value)}
          placeholder="Search saved comparisons"
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
        />
      </label>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
        {!error && !loading && items.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-slate-500">
            {query ? 'No comparisons match your search.' : 'Finished comparisons are saved here automatically.'}
          </p>
        )}
        {items.map((item) => (
          <Item key={item.id} item={item} active={item.id === activeId} onOpen={onOpen} onRename={onRename} onDelete={onDelete} />
        ))}
      </div>
    </aside>
  )
}
