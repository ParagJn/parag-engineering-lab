import { AlertTriangle, Circle, ClipboardCheck, FileCheck2, PowerOff } from 'lucide-react'
import type { ArtefactCard as Card } from '../api'
import type { ReviewStatus } from '../api'
import { authorLabel, count, money } from '../lib/format'
import { ReviewChip } from './ReviewChip'

export interface ArtefactCardProps {
  /** The plan's name for it. */
  name: string
  /** Null until the artefact has been written. */
  card: Card | null
  selected: boolean
  onOpen: (artefactId: string) => void
  /** Where its review stands, as the server computed it. Omitted when not loaded. */
  review?: ReviewStatus | null
}

/** An artefact a person does by hand (the deployment verification, the handover sign-off). A card that says so and points at the checklist, with the progress when it is known: never a failure, never "not written yet". */
export function ByHandCard({ name, description, progress }: { name: string; description: string; progress?: string | null }) {
  return (
    <li aria-label={`${name}: done by hand`} className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
      <span className="flex flex-wrap items-center gap-2">
        <ClipboardCheck size={14} aria-hidden /> <span className="font-semibold">{name}</span>
        <span className="rounded-full border border-sky-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-sky-800">Done by hand</span>
        {progress && <span className="text-xs">{progress}</span>}
      </span>
      <span className="mt-1 block text-xs">{description} Use the checklist below; no model is involved.</span>
    </li>
  )
}

/** An artefact that is part of the design but switched off. A grey card with the server's reason: nothing to press, nothing to run, and not a failure. */
export function NotEnabledCard({ name, reason }: { name: string; reason: string }) {
  return (
    <li aria-label={`${name}: not enabled`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
      <span className="flex flex-wrap items-center gap-2">
        <PowerOff size={14} aria-hidden /> <span className="font-semibold">{name}</span>
        <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-600">Not enabled</span>
      </span>
      <span className="mt-1 block text-xs">{reason}</span>
    </li>
  )
}

export function ArtefactCardView({ name, card, selected, onOpen, review }: ArtefactCardProps) {
  if (card === null || card.latest_version === null) {
    return (
      <li className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-3 py-2 text-sm text-slate-500">
        <Circle size={14} aria-hidden /> <span>{name}</span> <span className="ml-auto text-xs">not written yet</span>
      </li>
    )
  }
  return (
    <li>
      <button type="button" onClick={() => onOpen(card.id)} aria-pressed={selected}
        className={`w-full rounded-xl border px-3 py-2 text-left text-sm ${selected ? 'border-slate-900 bg-slate-50' : 'border-slate-200 bg-white hover:border-slate-400'}`}>
        <span className="flex flex-wrap items-center gap-2">
          <FileCheck2 size={14} aria-hidden className="text-emerald-700" />
          <span className="font-semibold">{name}</span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{card.id}</span>
          <span className="text-xs text-slate-500">version {card.latest_version}</span>
          {review !== undefined && <ReviewChip status={review} />}
          {card.flags > 0 && (
            <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-900" title="The scanner flagged something in this artefact">
              <AlertTriangle size={11} aria-hidden /> {count(card.flags, 'flag')}
            </span>
          )}
        </span>
        <span className="mt-1 block text-xs text-slate-500">
          by {authorLabel(card.author)} · {count(card.attempts ?? 0, 'attempt')} · {card.item_count > 0 ? `${count(card.item_count, 'item')} · ` : ''}cost {money(card.cost_usd)}
        </span>
      </button>
    </li>
  )
}
