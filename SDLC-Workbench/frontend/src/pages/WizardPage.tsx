import { Check, FileText, Trash2, Upload } from 'lucide-react'
import { useRef } from 'react'
import type { Catalogue, Connector, ModeInfo, Plan } from '../api/types'
import { CONNECTORS } from '../api/types'
import { SimulatedBadge, ModeChip } from '../components/Badges'
import { Notice } from '../components/Notice'
import { PasteBox } from '../components/PasteBox'
import { CONNECTOR_LABEL, bytes, count } from '../lib/format'
import { MAX_BRIEF_CHARS, MAX_NAME_CHARS, STEPS, STEP_LABEL, stepProblem, type WizardState } from '../lib/wizard'

export interface WizardProps {
  state: WizardState
  catalogue: Catalogue
  modeInfo: ModeInfo
  plan: Plan | null
  planError: string | null
  submitError: string | null
  submitting: boolean
  /** Set when the wizard was opened from "Load the sample project": the note says the policy file goes in too. */
  sample?: { filename: string } | null
  onChange: (patch: Partial<Pick<WizardState, 'name' | 'brief'>>) => void
  onToggleArtefact: (phase: string, artefact: string) => void
  onToggleConnector: (connector: Connector) => void
  /** Files chosen in the Context step, and text pasted there. Nothing is sent until the project is created. */
  onAddFiles?: (files: File[]) => void
  onPasteDocument?: (filename: string, text: string) => void
  onRemoveDocument?: (key: string) => void
  /** A sentence about a file that could not be staged. */
  documentProblem?: string | null
  onBack: () => void
  onNext: () => void
  onCreate: () => void
}

function Stepper({ state }: { state: WizardState }) {
  const current = STEPS.indexOf(state.step)
  return (
    <ol aria-label="Steps" className="mb-5 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-sm">
      {STEPS.map((step, i) => (
        <li key={step} aria-current={i === current ? 'step' : undefined} className={i === current ? 'font-bold text-slate-900' : i < current ? 'text-emerald-700' : 'text-slate-400'}>
          {i < current ? <Check size={14} className="mr-1 inline" aria-hidden /> : null}{i + 1} {STEP_LABEL[step]}
        </li>
      ))}
    </ol>
  )
}

export function WizardPage(props: WizardProps) {
  const { state, catalogue, modeInfo, plan } = props
  const picker = useRef<HTMLInputElement>(null)
  const problem = stepProblem(state)
  const last = state.step === 'review'
  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold">New project</h1>
      <Stepper state={state} />
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        {state.step === 'basics' && (
          <div className="space-y-4">
            <div>
              <label htmlFor="p-name" className="block text-sm font-semibold">Project name</label>
              <input id="p-name" value={state.name} maxLength={MAX_NAME_CHARS + 40} onChange={(e) => props.onChange({ name: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
            </div>
            <div>
              <label htmlFor="p-brief" className="block text-sm font-semibold">Brief</label>
              <p className="text-xs text-slate-500">A paragraph: who uses it, what it must do, and any constraints. Agents treat this as the whole truth about what is wanted.</p>
              <textarea id="p-brief" rows={6} value={state.brief} onChange={(e) => props.onChange({ brief: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
              <p className="text-right text-xs text-slate-400">{state.brief.length} / {MAX_BRIEF_CHARS}</p>
            </div>
          </div>
        )}

        {state.step === 'mode' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2"><ModeChip mode={modeInfo.mode} /><span className="text-sm font-semibold">This server is in {modeInfo.mode.toUpperCase()} mode.</span></div>
            <p className="text-sm text-slate-700">{modeInfo.meaning}</p>
            <p className="text-sm text-slate-500">The mode belongs to the server, not to a project, so it cannot be changed here. It is shown on every screen.</p>
          </div>
        )}

        {state.step === 'produce' && (
          <div className="space-y-5">
            <p className="text-sm text-slate-600">Tick what each phase should produce. Required items cannot be switched off. Items in the same wave run at the same time.</p>
            {catalogue.phases.map((phase) => {
              const planned = plan?.phases.find((p) => p.key === phase.key)
              return (
                <fieldset key={phase.key} className="rounded-lg border border-slate-200 p-3">
                  <legend className="px-1 text-sm font-bold">{phase.name}</legend>
                  <div className="grid gap-1 sm:grid-cols-2">
                    {phase.artefacts.map((a) => {
                      const on = (state.ticked[phase.key] ?? []).includes(a.key)
                      const wave = planned?.artefacts.find((x) => x.key === a.key)?.wave
                      return (
                        <label key={a.key} className="flex items-start gap-2 text-sm">
                          <input type="checkbox" checked={on} disabled={a.required} onChange={() => props.onToggleArtefact(phase.key, a.key)} className="mt-1" />
                          <span>
                            {a.name}{a.required ? <em className="not-italic text-slate-400"> (required)</em> : null}
                            {wave ? <span className="text-xs text-slate-400"> · wave {wave}</span> : null}
                          </span>
                        </label>
                      )
                    })}
                  </div>
                </fieldset>
              )
            })}
            {plan && plan.notes.length > 0 && <Notice tone="info" title="Added for you">{plan.notes.map((n) => <p key={n}>{n}</p>)}</Notice>}
            {props.planError && <Notice tone="error" title="This selection cannot be used">{props.planError}</Notice>}
          </div>
        )}

        {state.step === 'context' && (
          <div className="space-y-2">
            <p className="text-sm font-semibold">Reference documents</p>
            <p className="text-sm text-slate-600">Add the documents the agents should work from, such as a policy, a spec or earlier notes. They are added when the project is created, and you can add or remove more on the project page.</p>
            {props.sample && <Notice tone="info" title="The sample project includes a document">{props.sample.filename} will be added for you when the project is created.</Notice>}
            <div>
              <input ref={picker} type="file" multiple accept=".txt,.md,.markdown,.docx,.pdf" className="sr-only" aria-label="Choose documents to add"
                onChange={(e) => { props.onAddFiles?.(Array.from(e.target.files ?? [])); e.target.value = '' }} />
              <button type="button" onClick={() => picker.current?.click()} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold">
                <Upload size={14} aria-hidden /> Choose files
              </button>
              <span className="ml-2 text-xs text-slate-500">.txt, .md, .docx or .pdf, up to 10 MB each</span>
            </div>
            <PasteBox onAdd={(name, text) => props.onPasteDocument?.(name, text)} disabled={false} idPrefix="wizard" />
            {props.documentProblem && <Notice tone="warn" title="That file was not added">{props.documentProblem}</Notice>}
            {state.documents.length > 0 && (
              <ul aria-label="Documents to add" className="list-none space-y-1 p-0">
                {state.documents.map((d) => (
                  <li key={d.key} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm">
                    <FileText size={14} aria-hidden className="text-slate-400" />
                    <span className="font-semibold">{d.filename}</span>
                    <span className="text-xs text-slate-500">{bytes(d.size)}</span>
                    <button type="button" onClick={() => props.onRemoveDocument?.(d.key)} aria-label={`Do not add ${d.filename}`}
                      className="ml-auto inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2 py-1 text-xs text-rose-700"><Trash2 size={12} aria-hidden /> Remove</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {state.step === 'connectors' && (
          <div className="space-y-3">
            <Notice tone="warn" title="Nothing is connected">These connectors are simulated. Ticking one is noted in the audit trail and changes nothing.</Notice>
            {CONNECTORS.map((c) => (
              <label key={c} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={state.connectors.includes(c)} onChange={() => props.onToggleConnector(c)} />
                {CONNECTOR_LABEL[c]} <SimulatedBadge />
              </label>
            ))}
          </div>
        )}

        {state.step === 'review' && (
          <div className="space-y-3 text-sm">
            <p><strong>{state.name.trim()}</strong> <ModeChip mode={modeInfo.mode} /></p>
            {state.brief && <p className="whitespace-pre-wrap text-slate-700">{state.brief}</p>}
            {plan && <p className="text-slate-600">{count(plan.phases.reduce((n, p) => n + p.artefacts.length, 0), 'artefact')} across {count(plan.phases.length, 'phase')}.</p>}
            {(state.documents.length > 0 || props.sample) && <p className="text-slate-600">{count(state.documents.length + (props.sample ? 1 : 0), 'document')} will be added: {[...(props.sample ? [props.sample.filename] : []), ...state.documents.map((d) => d.filename)].join(', ')}.</p>}
            {state.connectors.length > 0 && <p className="text-slate-600">Simulated connectors noted: {state.connectors.map((c) => CONNECTOR_LABEL[c]).join(', ')}.</p>}
            {props.submitError && <Notice tone="error" title="The project was not created">{props.submitError}</Notice>}
          </div>
        )}
      </div>

      {problem && <p role="alert" className="mt-2 text-sm text-rose-700">{problem}</p>}
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={props.onBack} disabled={state.step === 'basics'} className="rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:opacity-40">Back</button>
        {last ? (
          <button type="button" onClick={props.onCreate} disabled={props.submitting || !!props.planError} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {props.submitting ? 'Creating…' : 'Create project'}
          </button>
        ) : (
          <button type="button" onClick={props.onNext} disabled={!!problem || (state.step === 'produce' && !!props.planError)} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Next</button>
        )}
      </div>
    </section>
  )
}
