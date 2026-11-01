import type { ReviewerOption } from '../api'
import { pricePerMillion } from '../lib/format'
import { Notice } from './Notice'

export interface FamilyPickerProps {
  /** The reviewer that could not run. */
  slot: string
  options: ReviewerOption[]
  chosen: string | null
  busy: boolean
  onChoose: (slot: string) => void
  onReview: () => void
}

/** The reviewer could not run. The person picks another model family; nothing is switched for them. */
export function FamilyPicker({ slot, options, chosen, busy, onChoose, onReview }: FamilyPickerProps) {
  if (options.length === 0) {
    return <Notice tone="error" title={`The ${slot} reviewer could not run`}>No other model family is configured to review with. Add one to the server's settings and try again.</Notice>
  }
  return (
    <fieldset className="rounded-xl border border-amber-300 bg-amber-50 p-3">
      <legend className="px-1 text-sm font-bold text-amber-900">The {slot} reviewer could not run. Choose another model family to review with.</legend>
      <ul className="list-none space-y-1 p-0">
        {options.map((o) => (
          <li key={o.slot}>
            <label className="flex flex-wrap items-center gap-2 rounded-lg px-2 py-1 text-sm">
              <input type="radio" name="reviewer-family" value={o.slot} checked={chosen === o.slot} onChange={() => onChoose(o.slot)} />
              <span className="font-semibold">{o.family}</span>
              <span className="font-mono text-xs text-slate-600">{o.model_id}</span>
              <span className={`rounded-full border px-2 py-0.5 text-xs ${o.independent === true ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : o.independent === false ? 'border-amber-300 bg-white text-amber-900' : 'border-slate-300 bg-white text-slate-700'}`}>
                {o.independent === true ? 'independent of the writer' : o.independent === false ? 'same family as the writer' : 'independence unverified'}
              </span>
              <span className="text-xs text-slate-600">input {pricePerMillion(o.price_input)} · output {pricePerMillion(o.price_output)} per million tokens{o.priced ? '' : ' (no price set)'}</span>
            </label>
          </li>
        ))}
      </ul>
      <button type="button" onClick={onReview} disabled={busy || chosen === null} className="mt-2 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
        {busy ? 'Reviewing…' : 'Review with the chosen family'}
      </button>
    </fieldset>
  )
}
