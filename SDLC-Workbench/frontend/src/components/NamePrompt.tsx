import { useState } from 'react'
import { MAX_NAME, OTHER, nameProblem, startingChoice, valueForChoice } from '../lib/actor'

/** Asked once. The name goes into the audit trail; it is a label, not a sign-in, and the screen says so. */
export function NamePrompt({ initial, names = [], onSave, onCancel }: { initial: string; names?: string[]; onSave: (name: string) => void; onCancel?: () => void }) {
  const [choice, setChoice] = useState(() => startingChoice(initial, names))
  const [value, setValue] = useState(() => (names.length === 0 || startingChoice(initial, names) === OTHER ? initial : startingChoice(initial, names)))
  const listed = names.length > 0
  const typing = !listed || choice === OTHER
  const pick = (next: string) => { setChoice(next); setValue(valueForChoice(next)) }
  const problem = value ? nameProblem(value) : null
  return (
    <form
      className="mx-auto mt-16 max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-panel"
      onSubmit={(e) => { e.preventDefault(); if (!nameProblem(value)) onSave(value) }}
    >
      <h1 className="mb-1 text-xl font-bold">What should we call you?</h1>
      <p className="mb-4 text-sm text-slate-600">
        Your name goes in the audit trail next to anything you approve, reject or edit. It is a label, not a sign-in: there is no password,
        and it stays in this browser.
      </p>
      {listed && (
        <>
          <label className="block text-sm font-semibold" htmlFor="actor-pick">Name</label>
          <select id="actor-pick" autoFocus value={choice} onChange={(e) => pick(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
            <option value="" disabled>Choose your name</option>
            {names.map((n) => <option key={n} value={n}>{n}</option>)}
            <option value={OTHER}>Someone else (type a name)</option>
          </select>
        </>
      )}
      {typing && (
        <>
          <label className={`block text-sm font-semibold ${listed ? 'mt-3' : ''}`} htmlFor="actor-name">{listed ? 'Your name' : 'Name'}</label>
          <input
            id="actor-name" autoFocus={!listed} value={value} maxLength={MAX_NAME + 20} onChange={(e) => setValue(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </>
      )}
      {problem && <p role="alert" className="mt-1 text-sm text-rose-700">{problem}</p>}
      <div className="mt-4 flex gap-2">
        <button type="submit" disabled={!value || !!nameProblem(value)} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Continue</button>
        {onCancel && <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>}
      </div>
    </form>
  )
}
