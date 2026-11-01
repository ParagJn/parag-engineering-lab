import { ArrowLeft, Download } from 'lucide-react'
import type { Gap, TraceItem, TraceRow, Traceability } from '../api/trace'
import { EMPTY_CELL, GROUP_HINT, GROUP_TITLE, KIND_TITLE, byGroup, byKind, cellText, csvPath, headline, layerName, rowSummary } from '../lib/trace'
import { buildHash } from '../lib/router'
import { Notice } from './Notice'

const itemHref = (projectId: string, item: string) => buildHash({ name: 'traceability', id: projectId, item })

/** An item ID as a link to its own page. The name beside it is the writer's own words, shown as text. */
function ItemLink({ projectId, id, name }: { projectId: string; id: string; name?: string }) {
  return (
    <a href={itemHref(projectId, id)} className="font-mono text-xs text-sky-800 underline" title={name || undefined}>{id}</a>
  )
}

function GapRow({ gap, projectId }: { gap: Gap; projectId: string }) {
  return (
    <li className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
      <p>{gap.sentence}</p>
      <p className="mt-0.5 text-xs text-slate-500">
        <ItemLink projectId={projectId} id={gap.item} /> in <span className="font-mono">{gap.artefact_id}</span>, version {gap.version}
        {gap.other ? <> · points at <span className="font-mono">{gap.other}</span></> : null}
      </p>
    </li>
  )
}

/** The gaps, first, because that is what an approver wants to see. Two groups, no colours of severity: a gap is a fact the server computed. */
export function GapList({ gaps, more, projectId }: { gaps: Gap[]; more: number; projectId: string }) {
  const groups = byGroup(gaps)
  if (gaps.length === 0) return <p role="status" className="text-sm text-emerald-800">Nothing is missing: every item that should be accounted for is.</p>
  return (
    <div className="space-y-4">
      {(['needs_attention', 'explained'] as const).map((group) => groups[group].length > 0 && (
        <section key={group} aria-label={GROUP_TITLE[group]}>
          <h3 className="text-sm font-bold">{GROUP_TITLE[group]} ({groups[group].length})</h3>
          <p className="text-xs text-slate-500">{GROUP_HINT[group]}</p>
          {byKind(groups[group]).map(({ kind, gaps: ofKind }) => (
            <div key={kind} className="mt-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{KIND_TITLE[kind]} ({ofKind.length})</h4>
              <ul className="mt-1 list-none space-y-1.5 p-0">{ofKind.map((g, i) => <GapRow key={`${g.item}-${g.by ?? g.other ?? i}-${i}`} gap={g} projectId={projectId} />)}</ul>
            </div>
          ))}
        </section>
      ))}
      {more > 0 && <p className="text-xs text-slate-500">And {more} more that are not listed. Fix these first and the rest will show.</p>}
    </div>
  )
}

/** One row per requirement, one column per kind of thing built on it. An empty cell is a dash, never blank. */
export function ChainTable({ data, projectId }: { data: Traceability; projectId: string }) {
  if (data.chains.length === 0) return <p className="text-sm text-slate-600">There are no requirements yet. Run the Requirements phase first.</p>
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-left text-xs">
        <caption className="sr-only">Each requirement and what was built for it</caption>
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th scope="col" className="sticky left-0 bg-slate-50 px-3 py-2">Requirement</th>
            {data.layers.map((layer) => <th key={layer} scope="col" className="px-3 py-2" title={layer}>{layerName(layer)}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.chains.map((chain) => (
            <tr key={chain.item} className="border-t border-slate-100 align-top">
              <th scope="row" className="sticky left-0 max-w-[16rem] bg-white px-3 py-2 font-normal">
                <ItemLink projectId={projectId} id={chain.item} name={chain.name} />
                <span className="block text-slate-600">{chain.name}</span>
                <span className="block text-[11px] text-slate-400">{rowSummary(chain.cells)}</span>
              </th>
              {chain.cells.map((cell) => (
                <td key={cell.layer} className={`px-3 py-2 ${cell.state === 'empty' ? 'text-rose-700' : cell.state === 'not_started' ? 'text-slate-400' : ''}`}>
                  {cell.state === 'built'
                    ? cell.items.map((id, i) => <span key={id}>{i > 0 ? ' ' : ''}<ItemLink projectId={projectId} id={id} name={data.names[id]} /></span>)
                    : <span aria-label={cell.state === 'empty' ? 'nothing built' : 'not started'}>{cellText(cell)}</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Rows({ rows, projectId, empty }: { rows: TraceRow[]; projectId: string; empty: string }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500">{empty}</p>
  return (
    <ul className="m-0 list-none space-y-1 p-0 text-sm">
      {rows.map((r) => (
        <li key={r.id}>
          {r.known ? <ItemLink projectId={projectId} id={r.id} name={r.name} /> : <span className="font-mono text-xs">{r.id}</span>}
          {r.name ? <span className="text-slate-600"> {r.name}</span> : null}
          {r.withdrawn ? <span className="ml-1 rounded bg-amber-100 px-1 text-[11px] text-amber-900">withdrawn</span> : null}
          {!r.known ? <span className="ml-1 text-[11px] text-slate-500">not an item in this project</span> : null}
        </li>
      ))}
    </ul>
  )
}

/** One item with what it comes from and what was built on it, nearest first. */
export function ItemTrace({ trace, projectId }: { trace: TraceItem; projectId: string }) {
  return (
    <section aria-label={`Trace of ${trace.item.id}`} className="space-y-4">
      <header>
        <h2 className="text-lg font-bold"><span className="font-mono">{trace.item.id}</span> {trace.item.name}</h2>
        {trace.item.artefact_id && <p className="text-xs text-slate-500">in <span className="font-mono">{trace.item.artefact_id}</span></p>}
      </header>
      {trace.gaps.length > 0 && <GapList gaps={trace.gaps} more={0} projectId={projectId} />}
      <div className="grid gap-6 sm:grid-cols-2">
        <div><h3 className="mb-1 text-sm font-bold">Comes from ({trace.comes_from.length})</h3><Rows rows={trace.comes_from} projectId={projectId} empty="Nothing: it starts the chain." /></div>
        <div><h3 className="mb-1 text-sm font-bold">Built on it ({trace.built_on_it.length})</h3><Rows rows={trace.built_on_it} projectId={projectId} empty="Nothing is built on it yet." /></div>
      </div>
    </section>
  )
}

/** The whole tab: a line saying how things stand, the gaps, the chain table, and the CSV. */
export function TraceabilityPanel({ data, projectId, projectName }: { data: Traceability; projectId: string; projectName: string }) {
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <a href={buildHash({ name: 'project', id: projectId, phase: null })} className="inline-flex items-center gap-1 text-sm text-sky-800 no-underline"><ArrowLeft size={14} aria-hidden /> Back to {projectName}</a>
          <h2 className="mt-1 text-xl font-bold">Traceability</h2>
          <p className="text-sm text-slate-700" role="status">{headline(data)}</p>
        </div>
        <a href={csvPath(projectId)} download className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-800 no-underline"><Download size={14} aria-hidden /> Download as CSV</a>
      </header>
      <section aria-label="Gaps"><h3 className="mb-2 text-base font-bold">Gaps</h3><GapList gaps={data.gaps} more={data.gaps_more} projectId={projectId} /></section>
      <section aria-label="Chain table">
        <h3 className="mb-1 text-base font-bold">What was built for each requirement</h3>
        <p className="mb-2 text-xs text-slate-500">A dash ({EMPTY_CELL}) means nothing was built for it there. Click an ID to see what it comes from and what is built on it.</p>
        <ChainTable data={data} projectId={projectId} />
      </section>
      <Notice tone="info">This is worked out from the links the artefacts declare, each time you open it. Nothing here is stored or asked of a model.</Notice>
    </div>
  )
}
