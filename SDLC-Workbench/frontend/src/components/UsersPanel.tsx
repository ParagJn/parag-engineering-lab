import { useState } from 'react'
import { Notice } from './Notice'
import type { UsersList, Me } from '../api/users'
import { approversChanged, approversFor, isLastAdministrator, newPerson, rolesFor, sortedUsers, toggleRole, whoLine } from '../lib/users'

const PHASE_NAMES: Record<string, string> = { setup: 'Setup', requirements: 'Requirements', design: 'Design', architecture: 'Architecture', build: 'Build & Test', deploy: 'Deploy', handover: 'BAU handover' }

export interface UsersPanelProps {
  list: UsersList
  me: Me | null
  /** Can this person change the list: an Administrator, or anyone while the list is empty. The server decides again on every change. */
  canEdit: boolean
  busy: boolean
  error: string | null
  onAdd: (name: string, roles: string[]) => void
  onRoles: (name: string, roles: string[]) => void
  onActive: (name: string, active: boolean) => void
  onApprovers: (phase: string, roles: string[]) => void
}

function RoleBoxes({ all, held, label, disabled, onChange }: { all: readonly string[]; held: readonly string[]; label: string; disabled: boolean; onChange: (roles: string[]) => void }) {
  return (
    <fieldset className="m-0 flex flex-wrap gap-x-3 gap-y-1 border-0 p-0" aria-label={label}>
      {all.map((role) => (
        <label key={role} className="inline-flex items-center gap-1 text-sm">
          <input type="checkbox" checked={held.includes(role)} disabled={disabled} onChange={() => onChange(toggleRole(all, held, role))} />
          {role}
        </label>
      ))}
    </fieldset>
  )
}

/** The Users and roles tab (S23c): who is on the list, what each person holds, and which roles may approve each phase. Plain text from the server, never markup. */
export function UsersPanel(p: UsersPanelProps) {
  const [name, setName] = useState('')
  const [newRoles, setNewRoles] = useState<string[]>([])
  const off = !p.canEdit || p.busy
  const users = sortedUsers(p.list.users)
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-600">{p.list.note}</p>
      {p.me && <p className="text-sm font-semibold" role="status">{whoLine(p.me)}</p>}
      {p.list.empty && <Notice tone="warn" title="Nobody is on the Users list yet">{p.list.empty_hint}</Notice>}
      {!p.canEdit && !p.list.empty && <Notice tone="info">Only an Administrator can change this list. You can read it.</Notice>}
      {p.error && <Notice tone="error" title="That could not be done">{p.error}</Notice>}

      <section aria-label="People" className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-2 text-base font-bold">People</h3>
        {users.length === 0 ? <p className="text-sm text-slate-500">No one yet.</p> : (
          <ul className="m-0 list-none space-y-3 p-0">
            {users.map((u) => {
              const last = isLastAdministrator(p.list.users, u.name)
              return (
                <li key={u.name} aria-label={`${u.name}${u.active ? '' : ' (switched off)'}`} className={`rounded-lg border p-3 ${u.active ? 'border-slate-200' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-semibold">{u.name}</span>
                    {!u.active && <span className="rounded-full border border-slate-300 px-2 py-0.5 text-[11px] font-semibold">Switched off</span>}
                    <button type="button" disabled={off || last} onClick={() => p.onActive(u.name, !u.active)} className="ml-auto rounded border border-slate-300 px-2 py-0.5 text-xs font-semibold disabled:opacity-40">
                      {u.active ? 'Switch off' : 'Switch on'}
                    </button>
                  </div>
                  <div className="mt-2"><RoleBoxes all={p.list.roles} held={u.roles} label={`Roles of ${u.name}`} disabled={off || !u.active} onChange={rolesFor(p.onRoles, u.name)} /></div>
                  {last && <p className="mt-1 text-xs text-slate-500">The last Administrator: this person cannot be switched off or lose the role until someone else has it.</p>}
                </li>
              )
            })}
          </ul>
        )}
        <form className="mt-4 space-y-2 border-t border-slate-100 pt-3" aria-label="Add a person" onSubmit={(e) => { e.preventDefault(); const made = newPerson(name, newRoles, off); if (made) { p.onAdd(made.name, made.roles); setName(''); setNewRoles([]) } }}>
          <label className="block text-sm font-semibold" htmlFor="new-user-name">Add a person</label>
          <input id="new-user-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} disabled={off} placeholder="Their name, as they will type it" className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40" />
          <RoleBoxes all={p.list.roles} held={newRoles} label="Roles for the new person" disabled={off} onChange={setNewRoles} />
          <button type="submit" disabled={off || !name.trim()} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">Add</button>
        </form>
      </section>

      <section aria-label="Who approves each phase" className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-1 text-base font-bold">Who approves each phase</h3>
        <p className="mb-3 text-xs text-slate-500">A person needs one of the ticked roles to approve a phase or send it back. Everything else stays open to anyone with a name. A phase always keeps at least one role.</p>
        <ul className="m-0 list-none space-y-3 p-0">
          {Object.keys(p.list.approvers).map((phase) => {
            const held = p.list.approvers[phase]
            return (
              <li key={phase} aria-label={`Approvers of ${PHASE_NAMES[phase] ?? phase}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{PHASE_NAMES[phase] ?? phase}</span>
                  {approversChanged(p.list, phase) && <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-900">Changed from the default</span>}
                </div>
                <RoleBoxes all={p.list.roles} held={held} label={`Roles that approve ${PHASE_NAMES[phase] ?? phase}`} disabled={off} onChange={approversFor(p.onApprovers, phase)} />
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
