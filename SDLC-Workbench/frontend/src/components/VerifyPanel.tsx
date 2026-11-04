import { ArrowLeft, Check, CheckCheck, Download, Eye, Plus, X, CircleHelp } from 'lucide-react'
import type { ReactElement } from 'react'
import type { Area, AreaCounts, VerifyDetail, VerifyMatch, VerifyRun } from '../api/verify'
import { AREA_WORDS, STATE_LOOK, STATE_ORDER, changeSince, howOf, percent, ringOf, shareFound, sparkline, tileLabel, tilesOf, trendOf, whereOf } from '../lib/verify'
import { buildHash } from '../lib/router'
import { count } from '../lib/format'
import { Notice } from './Notice'

const ICONS = { check: Check, 'check-alert': CheckCheck, help: CircleHelp, x: X, eye: Eye, plus: Plus } as const

/** The icon of a state: a shape, so the picture reads without colour. Hidden from a screen reader, which gets the words instead. */
export function StateIcon({ state, size = 16 }: { state: VerifyMatch['state']; size?: number }) {
  const Icon = ICONS[STATE_LOOK[state].icon]
  return <Icon size={size} aria-hidden />
}

/** One ring: how much of an area's design was found. The number is in the middle in words too, because a ring is only a picture. */
export function Ring({ counts }: { counts: AreaCounts }) {
  const share = shareFound(counts)
  const { circumference, drawn } = ringOf(share)
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" role="img" aria-label={counts.designed === 0 ? `${AREA_WORDS[counts.area]}: nothing in the design` : `${AREA_WORDS[counts.area]}: ${percent(share)} found`}>
      <circle cx="36" cy="36" r="28" fill="none" strokeWidth="8" className="stroke-slate-200" />
      {counts.designed > 0 && (
        <circle cx="36" cy="36" r="28" fill="none" strokeWidth="8" strokeLinecap="butt" strokeDasharray={`${drawn} ${circumference - drawn}`} transform="rotate(-90 36 36)" className="stroke-emerald-600" />
      )}
      <text x="36" y="41" textAnchor="middle" className="fill-slate-900 text-[15px] font-bold">{counts.designed === 0 ? '–' : percent(share)}</text>
    </svg>
  )
}

function Tile({ match }: { match: VerifyMatch }) {
  const look = STATE_LOOK[match.state]
  const where = whereOf(match)
  return (
    <li>
      <details className={`group rounded-lg border-2 ${look.tile}`}>
        <summary aria-label={tileLabel(match)} className="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1 text-xs font-semibold">
          <StateIcon state={match.state} size={14} />
          <span className="font-mono">{match.designed ?? match.built}</span>
        </summary>
        <div className="space-y-1 border-t border-current/20 px-2 py-2 text-xs font-normal text-slate-800">
          <p className="font-semibold">{look.word}</p>
          <p>{look.hint}</p>
          {match.designed && match.built && <p>Found as <span className="font-mono">{match.built}</span></p>}
          {match.designed === null && match.built && <p><span className="font-mono">{match.built}</span></p>}
          {where && <p>In <span className="font-mono">{where}</span></p>}
          {howOf(match) && <p>{howOf(match)}</p>}
          {match.differences.length > 0 && <ul className="list-disc pl-4">{match.differences.map((d, i) => <li key={i}>{d}</li>)}</ul>}
          {match.note && <p>{match.note}</p>}
        </div>
      </details>
    </li>
  )
}

export function AreaCard({ counts, matches, previous, newer }: { counts: AreaCounts; matches: readonly VerifyMatch[]; previous?: VerifyRun; newer: VerifyRun }) {
  const tiles = tilesOf(matches, counts.area)
  const change = changeSince(newer, previous, counts.area)
  return (
    <section aria-label={AREA_WORDS[counts.area]} className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-4">
        <Ring counts={counts} />
        <div>
          <h3 className="text-base font-bold">{AREA_WORDS[counts.area]}</h3>
          <p className="text-sm text-slate-600">
            {counts.designed === 0 ? 'Nothing in the design.' : `${counts.found + counts.differences} of ${counts.designed} found`}
            {counts.extras > 0 && <> · {counts.extras} built but not designed</>}
          </p>
          {change !== null && change !== 0 && <p className="text-xs text-slate-500">{change > 0 ? `${change} more` : `${-change} fewer`} found than in the run before</p>}
        </div>
      </div>
      {tiles.length > 0 && <ul aria-label={`${AREA_WORDS[counts.area]} items`} className="mt-3 flex list-none flex-wrap gap-1.5 p-0">{tiles.map((m, i) => <Tile key={`${m.designed ?? m.built}-${i}`} match={m} />)}</ul>}
    </section>
  )
}

/** What each colour and shape means, once, as words. */
export function Legend() {
  return (
    <ul aria-label="What the colours and shapes mean" className="flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-slate-700">
      {STATE_ORDER.map((s) => <li key={s} className="flex items-center gap-1"><span className={`inline-flex h-5 w-5 items-center justify-center rounded border-2 ${STATE_LOOK[s].tile}`}><StateIcon state={s} size={12} /></span>{STATE_LOOK[s].word}</li>)}
    </ul>
  )
}

function Trend({ runs }: { runs: readonly VerifyRun[] }) {
  if (runs.length < 2) return <p className="text-xs text-slate-500">Run the check again after more of the build is written to see how it moves.</p>
  return (
    <ul aria-label="How the share found moved over the runs" className="flex list-none flex-wrap gap-4 p-0">
      {(['endpoint', 'table', 'screen', 'rule'] as Area[]).map((area) => {
        const points = trendOf(runs, area)
        return (
          <li key={area} className="text-xs text-slate-700">
            <svg width="120" height="28" viewBox="0 0 120 28" role="img" aria-label={`${AREA_WORDS[area]}: ${points.map((p) => percent(p.share)).join(', then ')}`}>
              <polyline points={sparkline(points)} fill="none" strokeWidth="2" className="stroke-slate-700" />
            </svg>
            {AREA_WORDS[area]}
          </li>
        )
      })}
    </ul>
  )
}

export interface VerifyPanelProps {
  projectId: string
  projectName: string
  advice: string
  runs: readonly VerifyRun[]
  detail: VerifyDetail | null
  designChanged: boolean
  busy: boolean
  error: string | null
  backend: string
  frontend: string
  canRun: boolean
  onBackend: (v: string) => void
  onFrontend: (v: string) => void
  onRun: () => void
  onOpenRun: (id: number) => void
}

export function VerifyPanel(p: VerifyPanelProps): ReactElement {
  const newer = p.detail
  const older = newer ? p.runs.find((r) => r.id < newer.id) : undefined
  return (
    <div className="space-y-4">
      <a href={buildHash({ name: 'project', id: p.projectId, phase: null })} className="inline-flex items-center gap-1 text-sm text-sky-800"><ArrowLeft size={14} aria-hidden /> Back to {p.projectName}</a>
      <div>
        <h2 className="text-lg font-bold">Build Verify</h2>
        <p className="mt-1 text-sm text-slate-600">{p.advice || 'This shows how far the build has drifted from the design. It is a highlighter, not a pass or fail, and it never runs your code.'}</p>
        <p className="mt-1 text-xs text-slate-500">The folders are read as text on this computer only. Files that may hold a secret (.env, keys) are never read.</p>
      </div>
      <form className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4" aria-label="Check a build" onSubmit={(e) => { e.preventDefault(); if (p.canRun && p.backend.trim() && !p.busy) p.onRun() }}>
        <label className="block text-sm font-semibold" htmlFor="verify-backend">Backend folder</label>
        <input id="verify-backend" value={p.backend} onChange={(e) => p.onBackend(e.target.value)} placeholder="/Users/you/project/backend" spellCheck={false} maxLength={1000} className="w-full rounded-lg border border-slate-300 px-3 py-1.5 font-mono text-sm" />
        <label className="block text-sm font-semibold" htmlFor="verify-frontend">Frontend folder (optional)</label>
        <input id="verify-frontend" value={p.frontend} onChange={(e) => p.onFrontend(e.target.value)} placeholder="/Users/you/project/frontend" spellCheck={false} maxLength={1000} className="w-full rounded-lg border border-slate-300 px-3 py-1.5 font-mono text-sm" />
        <p className="text-xs text-slate-500">Python/FastAPI for the backend; React, Vue or plain JavaScript/TypeScript for the frontend, read by pattern. Other languages are not understood in this version.</p>
        <button type="submit" disabled={!p.canRun || !p.backend.trim() || p.busy} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">{p.busy ? 'Checking…' : 'Check the build'}</button>
        {!p.canRun && <p className="text-xs text-slate-500">Give your name first (top right) so the check can be recorded in your name.</p>}
      </form>
      {p.error && <Notice tone="error" title="The check could not be run">{p.error}</Notice>}
      {newer && p.designChanged && <Notice tone="warn" title="The design changed after this run">Check the build again to compare it with the design as it is now.</Notice>}
      {newer ? (
        <>
          <Legend />
          <p className="text-xs text-slate-500">Run {newer.id} by {newer.by.replace(/^human:/, '')} · {newer.at} · backend <span className="font-mono">{newer.backend_path}</span>{newer.frontend_path ? <> · frontend <span className="font-mono">{newer.frontend_path}</span></> : null}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {newer.counts.map((c) => <AreaCard key={c.area} counts={c} matches={newer.matches} previous={older} newer={newer} />)}
          </div>
          {newer.notes.length > 0 && (
            <details className="rounded-lg border border-slate-200 bg-white px-3 py-2">
              <summary className="cursor-pointer text-sm font-semibold">What could not be read ({count(newer.notes.length, 'note')})</summary>
              <ul className="mt-2 list-disc pl-5 text-sm">{newer.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </details>
          )}
          <div className="flex flex-wrap gap-3 text-sm">
            <a href={`/api/projects/${encodeURIComponent(p.projectId)}/verify/${newer.id}/download`} className="inline-flex items-center gap-1 text-sky-800 underline"><Download size={14} aria-hidden /> Download as Markdown</a>
            <a href={`/api/projects/${encodeURIComponent(p.projectId)}/verify/${newer.id}/download?format=json`} className="inline-flex items-center gap-1 text-sky-800 underline"><Download size={14} aria-hidden /> Download as JSON</a>
          </div>
        </>
      ) : <Notice tone="info" title="No check yet">Give the backend folder of the build and press Check the build.</Notice>}
      {p.runs.length > 0 && (
        <section aria-label="Earlier runs" className="rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="text-base font-bold">How it moved</h3>
          <div className="mt-2"><Trend runs={p.runs} /></div>
          <ul className="mt-3 list-none space-y-1 p-0 text-sm">
            {p.runs.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => p.onOpenRun(r.id)} aria-current={newer?.id === r.id ? 'true' : undefined} className={`underline ${newer?.id === r.id ? 'font-bold' : ''}`}>Run {r.id}</button>
                <span className="text-slate-500"> · {r.at} · {r.counts.map((c) => `${AREA_WORDS[c.area]} ${c.designed ? percent(shareFound(c)) : '–'}`).join(', ')}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
