import { Search } from 'lucide-react'
import type { SearchResult } from '../api'
import { Notice } from './Notice'

export interface SearchBoxProps {
  query: string
  onQuery: (q: string) => void
  onSearch: () => void
  searching: boolean
  result: SearchResult | null
  error: string | null
}

/** A way to check what the agents can find, with the ID each passage would be cited by. It calls no model. */
export function SearchBox({ query, onQuery, onSearch, searching, result, error }: SearchBoxProps) {
  return (
    <section aria-label="Search" className="space-y-3">
      <h3 className="text-base font-bold">Search the project</h3>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); onSearch() }}>
        <input value={query} onChange={(e) => onQuery(e.target.value)} aria-label="Search words" maxLength={400} placeholder="a word or a question"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <button type="submit" disabled={searching || !query.trim()} className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">
          <Search size={14} aria-hidden /> {searching ? 'Searching…' : 'Search'}
        </button>
      </form>
      <p className="text-xs text-slate-500">Searches the documents and the approved artefacts. It does not call a model.</p>
      {error && <Notice tone="error">{error}</Notice>}
      {result && result.hits.length === 0 && <p className="text-sm text-slate-600">Nothing matches “{result.query}”.</p>}
      {result && result.hits.length > 0 && (
        <ol className="list-none space-y-2 p-0">
          {result.hits.map((h) => (
            <li key={h.source_id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
              <p className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{h.source_id}</span>
                <span className="font-semibold">{h.title}</span>
                {h.heading_path && <span className="text-xs text-slate-500">{h.heading_path}</span>}
                {h.relevance !== null && h.coverage !== null && <span className="ml-auto text-xs text-slate-400">matches {Math.round(h.coverage * 100)}% of your words</span>}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-slate-700">{h.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
