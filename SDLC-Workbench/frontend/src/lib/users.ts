// What the Users screens and the Approve button need, as plain functions so they are tested without a browser (S23).
import type { AppUser, Me, UsersList } from '../api/users'

/** The sentence that goes beside a greyed Approve button, or null when this person may approve (or nothing is restricted). The words are the server's own. */
export function approveBlock(me: Me | null, phaseKey: string): string | null {
  if (!me || !me.list_in_force) return null
  return me.may_approve.includes(phaseKey) ? null : (me.why_not[phaseKey] ?? 'You are not allowed to approve this phase.')
}

/** The same rule for sending a phase back: the server gives the one reason for both, with "approved" in it, so the screen says it as it is. */
export const sendBackBlock = approveBlock

/** One line under the name in the header: who the app thinks you are. */
export function whoLine(me: Me | null): string {
  if (!me) return ''
  if (!me.list_in_force) return 'Nobody is on the Users list yet, so nothing is restricted.'
  if (!me.on_list) return `${me.name} is not on the Users list: you can work, but not approve.`
  return me.roles.length > 0 ? `${me.name} · ${me.roles.join(', ')}` : `${me.name} · no role`
}

/** The roles a person does NOT yet hold, in the fixed order, for the "add a role" choice. */
export function rolesToAdd(all: readonly string[], held: readonly string[]): string[] {
  return all.filter((r) => !held.includes(r))
}

/** Turn a role on or off in a list, keeping the fixed order and each role once. */
export function toggleRole(all: readonly string[], held: readonly string[], role: string): string[] {
  const next = held.includes(role) ? held.filter((r) => r !== role) : [...held, role]
  return all.filter((r) => next.includes(r))
}

/** What ticking a box does: the callback for ONE person or ONE phase, so a tick can never reach the wrong one. Plain, so a test can press it. */
export const rolesFor = (onRoles: (name: string, roles: string[]) => void, name: string) => (roles: string[]) => onRoles(name, roles)
export const approversFor = (onApprovers: (phase: string, roles: string[]) => void, phase: string) => (roles: string[]) => onApprovers(phase, roles)

/** Active people first (by name), then the switched-off ones, so the list a person works with comes first. */
export function sortedUsers(users: readonly AppUser[]): AppUser[] {
  return [...users].sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name))
}

/** Has this phase's approver rule been changed from the default? Used to show "changed" beside it. */
export function approversChanged(list: Pick<UsersList, 'approvers' | 'defaults'>, phaseKey: string): boolean {
  const a = list.approvers[phaseKey] ?? [], d = list.defaults[phaseKey] ?? []
  return a.length !== d.length || a.some((r, i) => r !== d[i])
}

/** Would switching this person off, or taking Administrator from them, leave nobody able to manage the list? The server refuses it; the screen says so first. */
export function isLastAdministrator(users: readonly AppUser[], name: string): boolean {
  const me = users.find((u) => u.name === name)
  if (!me || !me.active || !me.roles.includes('Administrator')) return false
  return users.filter((u) => u.active && u.roles.includes('Administrator')).length === 1
}

/** Should the Configuration link show in the phase rail? Only while the Setup phase is the one on screen. */
export const showConfiguration = (selectedPhase: string): boolean => selectedPhase === 'setup'

/** May this person change the Users list? An Administrator, or anyone while the list is empty (the server decides again on every change). */
export const canEditUsers = (list: Pick<UsersList, 'empty'> | null, me: Pick<Me, 'administrator'> | null): boolean => !!list && (list.empty || !!me?.administrator)

/** What the Add form sends: the name tidied, or null when there is nothing to add (blank, or a change is being saved). */
export function newPerson(name: string, roles: readonly string[], disabled: boolean): { name: string; roles: string[] } | null {
  const clean = name.trim()
  return disabled || !clean ? null : { name: clean, roles: [...roles] }
}

/** The calls the page makes for each change, as functions of the client and the typed name, so each can be tested with a fake client. */
export interface UsersCalls {
  addUser(actor: string, name: string, roles: string[]): Promise<unknown>
  setUserRoles(actor: string, name: string, roles: string[]): Promise<unknown>
  setUserActive(actor: string, name: string, active: boolean): Promise<unknown>
  setApprovers(actor: string, phase: string, roles: string[]): Promise<unknown>
}
export function usersActions(client: UsersCalls, actor: string, change: (what: () => Promise<unknown>) => void) {
  return {
    onAdd: (n: string, r: string[]) => change(() => client.addUser(actor, n, r)),
    onRoles: (n: string, r: string[]) => change(() => client.setUserRoles(actor, n, r)),
    onActive: (n: string, a: boolean) => change(() => client.setUserActive(actor, n, a)),
    onApprovers: (p: string, r: string[]) => change(() => client.setApprovers(actor, p, r)),
  }
}

/** One change: busy while it runs, the list reloaded after it, the server's own sentence kept when it is refused. Plain, so a test can follow every step. */
export async function runChange(
  what: () => Promise<unknown>,
  ui: { setBusy: (b: boolean) => void; setError: (m: string | null) => void; reload: () => Promise<unknown> },
): Promise<void> {
  ui.setBusy(true); ui.setError(null)
  try { await what(); await ui.reload() } catch (e) { ui.setError(e instanceof Error ? e.message : 'That could not be done.') } finally { ui.setBusy(false) }
}

/** Ask the server what a typed name may do. No name, no question; if it cannot be read the answer is null and the Approve button is simply not greyed (the server still decides). */
export function loadMe(client: { me(actor: string): Promise<Me> }, actor: string): Promise<Me | null> {
  return actor ? client.me(actor).catch(() => null) : Promise.resolve(null)
}
