import { useEffect, useRef, useState } from 'react'
import { Check, Pencil, Plus, Search, Trash2, X } from 'lucide-react'

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

  const commit = () => {
    const next = title.trim()
    setEditing(false)
    if (next && next !== item.title) onRename(item.id, next)
    else setTitle(item.title)
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1 rounded-lg p-2" style={{ background: 'var(--paper)', border: '1px solid var(--accent)' }}>
        <input
          autoFocus
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit()
            if (e.key === 'Escape') {
              setEditing(false)
              setTitle(item.title)
            }
          }}
          className="min-w-0 flex-1 bg-transparent text-sm font-medium outline-none"
          style={{ color: 'var(--ink)' }}
        />
        <button type="button" onClick={commit} title="Save" aria-label="Save name" style={{ color: 'var(--accent)' }}>
          <Check size={15} />
        </button>
      </div>
    )
  }

  const count = item.diagram_count
  const unfinished = item.drawn_count < count
  return (
    <div
      className="group relative rounded-lg p-3"
      style={{
        background: active ? 'var(--paper)' : 'transparent',
        border: `1px solid ${active ? 'var(--line)' : 'transparent'}`,
      }}
    >
      <button type="button" onClick={() => onOpen(item.id)} className="block w-full text-left">
        <span className="block break-words pr-12 text-sm font-medium leading-5">{item.title}</span>
        <span className="kicker mt-1.5 block truncate" style={{ letterSpacing: '0.06em' }}>
          {when(item.created_at)}  ·  {count} diagram{count === 1 ? '' : 's'}
          {unfinished && count > 0 ? `  ·  ${item.drawn_count} drawn` : ''}
        </span>
        <span className="mt-0.5 block truncate text-xs" style={{ color: 'var(--muted)' }}>
          {item.source_name}
        </span>
      </button>
      <div className={`absolute right-2 top-2 flex items-center gap-1.5 ${confirming ? '' : 'opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100'}`}>
        {confirming ? (
          <>
            <button
              type="button"
              onClick={() => onDelete(item.id)}
              className="rounded px-2 py-0.5 text-xs font-semibold"
              style={{ background: 'var(--accent)', color: 'var(--paper)' }}
            >
              Delete
            </button>
            <button type="button" onClick={() => setConfirming(false)} title="Cancel" aria-label="Cancel delete" style={{ color: 'var(--muted)' }}>
              <X size={14} />
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={() => setEditing(true)} title="Rename" aria-label="Rename" style={{ color: 'var(--muted)' }}>
              <Pencil size={14} />
            </button>
            <button type="button" onClick={() => setConfirming(true)} title="Delete" aria-label="Delete" style={{ color: 'var(--muted)' }}>
              <Trash2 size={14} />
            </button>
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

  const change = (value) => {
    setText(value)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => onQuery(value), 250)
  }

  return (
    <aside className="flex min-h-0 flex-col gap-3">
      <button type="button" className="btn btn-primary justify-center" onClick={onNew}>
        <Plus size={15} /> New document
      </button>
      <label className="field flex items-center gap-2" style={{ padding: '7px 10px' }}>
        <Search size={14} style={{ color: 'var(--muted)' }} />
        <input
          value={text}
          onChange={(e) => change(e.target.value)}
          placeholder="Search history"
          className="min-w-0 flex-1 bg-transparent text-[13px] outline-none"
          style={{ color: 'var(--ink)' }}
        />
      </label>
      <div className="kicker px-1">History</div>
      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto pr-1">
        {error && (
          <p className="rounded-md px-3 py-2 text-xs" style={{ background: 'var(--accent-soft)', color: 'var(--ink)' }}>
            {error}
          </p>
        )}
        {!error && !loading && items.length === 0 && (
          <p className="px-2 py-6 text-center text-[13px]" style={{ color: 'var(--muted)' }}>
            {query ? 'Nothing matches your search.' : 'Your documents and their diagrams are saved here automatically.'}
          </p>
        )}
        {items.map((item) => (
          <Item key={item.id} item={item} active={item.id === activeId} onOpen={onOpen} onRename={onRename} onDelete={onDelete} />
        ))}
      </div>
    </aside>
  )
}
