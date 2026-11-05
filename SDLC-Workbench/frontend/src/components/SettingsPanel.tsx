import { RotateCcw } from 'lucide-react'
import { Notice } from './Notice'
import type { SettingEntry, SettingsView } from '../api/settings'
import { boxValue, canSave, changedIn, defaultNote, editNotice, editedCount, inputType, isEdited, restartBanner, savedSentence, secretWords, type Draft } from '../lib/settings'

export interface SettingsPanelProps {
  view: SettingsView
  draft: Draft
  busy: boolean
  error: string | null
  problems: string[]
  onChange: (key: string, value: string) => void
  onReset: (key: string) => void
  onSave: () => void
  onDiscard: () => void
  onRestore: (name: string) => void
}

function Box({ s, draft, disabled, onChange }: { s: SettingEntry; draft: Draft; disabled: boolean; onChange: (v: string) => void }) {
  const id = `setting-${s.key}`
  const value = boxValue(s, draft)
  if (s.kind === 'yes_no') {
    return <select id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1 text-sm disabled:opacity-40"><option value="true">Yes</option><option value="false">No</option></select>
  }
  if (s.kind === 'choice') {
    return <select id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1 text-sm disabled:opacity-40">{s.choices.map((c) => <option key={c} value={c}>{c}</option>)}</select>
  }
  return (
    <input id={id} type={inputType(s)} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} autoComplete="off" spellCheck={false} maxLength={2000}
      placeholder={s.secret ? (s.is_set ? 'Type a new value to replace it' : 'Type a value') : ''} className="w-full rounded-lg border border-slate-300 px-3 py-1 font-mono text-sm disabled:opacity-40" />
  )
}

/** The System settings tab (S23d, S23e). Every word on it comes from the server; a secret is shown only as Set or Not set, and its box starts empty. Text from the server is shown as text. */
export function SettingsPanel(p: SettingsPanelProps) {
  const off = !p.view.can_edit || !p.view.editable || p.busy
  const notice = editNotice(p.view)
  const banner = restartBanner(p.view)
  const edited = editedCount(p.view, p.draft)
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-600">{p.view.note}</p>
      {banner && <Notice tone="warn" title="Restart needed">{banner}</Notice>}
      {p.view.saved && <Notice tone="info" title="Saved">{savedSentence(p.view.saved)}</Notice>}
      {notice && <Notice tone="info">{notice}</Notice>}
      {p.error && (
        <Notice tone="error" title="That could not be saved">
          {p.error}
          {p.problems.length > 0 && <ul className="mt-1 list-disc pl-5">{p.problems.map((m, i) => <li key={i}>{m}</li>)}</ul>}
        </Notice>
      )}

      {p.view.groups.map((g) => (
        <section key={g.key} aria-label={g.title} className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="text-base font-bold">{g.title}{changedIn(g.settings) > 0 && <span className="ml-2 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-900">{changedIn(g.settings)} changed from the default</span>}</h3>
          <p className="mb-3 text-xs text-slate-500">{g.help}</p>
          <ul className="m-0 list-none space-y-3 p-0">
            {g.settings.map((s) => {
              const note = defaultNote(s)
              return (
                <li key={s.key} aria-label={s.label} className="grid gap-1 md:grid-cols-[240px_1fr]">
                  <div>
                    <label htmlFor={`setting-${s.key}`} className="text-sm font-semibold">{s.label}</label>
                    <p className="font-mono text-[11px] text-slate-400">{s.env_name}</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Box s={s} draft={p.draft} disabled={off} onChange={(v) => p.onChange(s.key, v)} />
                      {s.secret && <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${s.is_set ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-slate-300 bg-slate-50 text-slate-600'}`}>{secretWords(s)}</span>}
                      {s.unit && !s.secret && <span className="shrink-0 text-xs text-slate-500">{s.unit}</span>}
                      {isEdited(s, p.draft) && <button type="button" aria-label={`Undo the change to ${s.label}`} onClick={() => p.onReset(s.key)} className="shrink-0 rounded border border-slate-300 p-1 text-slate-600"><RotateCcw size={12} aria-hidden /></button>}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{s.help}{note ? ` ${note}.` : ''}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      ))}

      <div role="group" aria-label="Save" className="sticky bottom-0 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <button type="button" disabled={!canSave(p.view, p.draft, p.busy)} onClick={p.onSave} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">{p.busy ? 'Saving…' : 'Save'}</button>
        <button type="button" disabled={edited === 0 || p.busy} onClick={p.onDiscard} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold disabled:opacity-40">Discard changes</button>
        <span role="status" className="text-sm text-slate-600">{edited === 0 ? 'No changes yet.' : `${edited} ${edited === 1 ? 'setting' : 'settings'} changed.`}</span>
      </div>

      {p.view.backups.length > 0 && (
        <section aria-label="Earlier versions" className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="text-base font-bold">Earlier versions</h3>
          <p className="mb-2 text-xs text-slate-500">Before every save the old settings file is copied here (the last 10 are kept). Restoring one also needs a restart.</p>
          <ul className="m-0 list-none space-y-1 p-0">
            {p.view.backups.map((b) => (
              <li key={b.name} className="flex items-center gap-3 text-sm">
                <span className="font-mono text-xs">{b.name}</span>
                <button type="button" disabled={off} onClick={() => p.onRestore(b.name)} className="ml-auto rounded border border-slate-300 px-2 py-0.5 text-xs font-semibold disabled:opacity-40">Restore</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
