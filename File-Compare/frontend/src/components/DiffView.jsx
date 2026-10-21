import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import { getDiff } from '../api'

const CONTEXT = 2 // unchanged lines kept around each change in "changes only" mode

const cellTone = {
  delete: { a: 'bg-red-50', b: 'bg-slate-50' },
  insert: { a: 'bg-slate-50', b: 'bg-emerald-50' },
  replace: { a: 'bg-red-50', b: 'bg-emerald-50' },
  equal: { a: '', b: '' },
}

function Cell({ side, kind, which }) {
  const tone = cellTone[kind][which]
  if (!side) return <div className={`min-w-0 px-3 py-1 ${tone}`} />
  const mark = which === 'a' ? 'bg-red-200 text-red-950' : 'bg-emerald-200 text-emerald-950'
  return (
    <div className={`flex min-w-0 gap-3 px-3 py-1 ${tone}`}>
      <span className="w-8 shrink-0 select-none text-right text-xs tabular-nums leading-6 text-slate-400">{side.n}</span>
      <p className="min-w-0 flex-1 whitespace-pre-wrap break-words text-[13px] leading-6 text-slate-800">
        {side.segs
          ? side.segs.map(([text, changed], i) =>
              changed ? (
                <mark key={i} className={`rounded-sm px-0.5 ${mark}`}>
                  {text}
                </mark>
              ) : (
                <span key={i}>{text}</span>
              ),
            )
          : side.text}
      </p>
    </div>
  )
}

/** Turn rows into render items, folding long unchanged runs when `changesOnly` is on. */
function buildItems(rows, changesOnly) {
  const keep = new Array(rows.length).fill(!changesOnly)
  if (changesOnly) {
    rows.forEach((row, i) => {
      if (row.kind === 'equal') return
      for (let k = Math.max(0, i - CONTEXT); k <= Math.min(rows.length - 1, i + CONTEXT); k += 1) keep[k] = true
    })
  }
  const items = []
  let hidden = 0
  let previousKind = 'equal'
  rows.forEach((row, i) => {
    if (!keep[i]) {
      hidden += 1
      return
    }
    if (hidden) {
      items.push({ type: 'fold', count: hidden, key: `fold-${i}` })
      hidden = 0
    }
    // A "change group" starts at the first non-equal row after an equal row (or the start).
    const starts = row.kind !== 'equal' && previousKind === 'equal'
    items.push({ type: 'row', row, key: `row-${i}`, groupStart: starts })
    previousKind = row.kind
  })
  if (hidden) items.push({ type: 'fold', count: hidden, key: 'fold-end' })
  return items
}

export default function DiffView({ comparisonId, nameA, nameB }) {
  const [diff, setDiff] = useState(null)
  const [error, setError] = useState('')
  const [changesOnly, setChangesOnly] = useState(true)
  const [current, setCurrent] = useState(-1)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!comparisonId) return undefined
    let cancelled = false
    setDiff(null)
    setError('')
    setCurrent(-1)
    getDiff(comparisonId)
      .then((data) => {
        if (cancelled) return
        setDiff(data)
        setChangesOnly(true)
      })
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [comparisonId])

  const items = useMemo(() => (diff ? buildItems(diff.rows, changesOnly) : []), [diff, changesOnly])
  const groupCount = useMemo(() => items.filter((i) => i.groupStart).length, [items])

  function jump(direction) {
    if (!groupCount) return
    const next = current < 0 ? (direction > 0 ? 0 : groupCount - 1) : (current + direction + groupCount) % groupCount
    setCurrent(next)
    containerRef.current?.querySelector(`[data-group="${next}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }

  if (!comparisonId) {
    return <p className="text-sm text-slate-500">The side-by-side view needs a saved comparison, and this one could not be saved.</p>
  }
  if (error) return <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
  if (!diff) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 size={16} className="animate-spin" />
        Building the diff...
      </div>
    )
  }

  let groupIndex = -1
  const s = diff.stats
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-800">{s.replace} changed</span>
          <span className="rounded-full bg-red-50 px-2.5 py-1 text-red-700">{s.delete} only in A</span>
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">{s.insert} only in B</span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">{s.equal} unchanged</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-2 text-xs font-bold text-slate-700">
            <input type="checkbox" className="accent-slate-950" checked={changesOnly} onChange={(e) => setChangesOnly(e.target.checked)} />
            Changes only
          </label>
          <span className="text-xs tabular-nums text-slate-500">{groupCount ? `${current < 0 ? '–' : current + 1} / ${groupCount}` : 'no changes'}</span>
          <button
            onClick={() => jump(-1)}
            disabled={!groupCount}
            title="Previous change"
            className="grid h-8 w-8 place-items-center rounded-md border border-slate-200 text-slate-700 transition hover:border-slate-500 disabled:opacity-40"
          >
            <ChevronUp size={16} />
          </button>
          <button
            onClick={() => jump(1)}
            disabled={!groupCount}
            title="Next change"
            className="grid h-8 w-8 place-items-center rounded-md border border-slate-200 text-slate-700 transition hover:border-slate-500 disabled:opacity-40"
          >
            <ChevronDown size={16} />
          </button>
        </div>
      </div>

      {!groupCount ? (
        <p className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">The two files have identical text.</p>
      ) : (
        <div ref={containerRef} className="max-h-[70vh] overflow-auto rounded-lg border border-slate-200">
          <div className="sticky top-0 z-10 grid grid-cols-2 border-b border-slate-200 bg-slate-50 text-xs font-bold text-slate-700">
            <div className="truncate px-3 py-2">A · {nameA}</div>
            <div className="truncate border-l border-slate-200 px-3 py-2">B · {nameB}</div>
          </div>
          {items.map((item) => {
            if (item.type === 'fold') {
              return (
                <div key={item.key} className="border-y border-slate-100 bg-slate-50 px-3 py-1 text-center text-xs text-slate-400">
                  {item.count} unchanged {item.count === 1 ? 'line' : 'lines'}
                </div>
              )
            }
            if (item.groupStart) groupIndex += 1
            const active = item.groupStart && groupIndex === current
            return (
              <div
                key={item.key}
                data-group={item.groupStart ? groupIndex : undefined}
                className={`grid grid-cols-2 divide-x divide-slate-100 ${active ? 'ring-2 ring-inset ring-slate-900' : ''}`}
              >
                <Cell side={item.row.a} kind={item.row.kind} which="a" />
                <Cell side={item.row.b} kind={item.row.kind} which="b" />
              </div>
            )
          })}
        </div>
      )}
      <p className="mt-2 text-xs text-slate-500">
        Compares extracted text line by line. Highlighted words changed inside a line; blank lines and surrounding spaces are ignored.
      </p>
    </div>
  )
}
