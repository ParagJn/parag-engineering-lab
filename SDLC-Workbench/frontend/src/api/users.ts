// Users and roles (S23): who is on the list, what roles they hold, which roles may approve which phase, and what a typed name may do.
// The server decides all of it; the screen only shows it. A name is a label, not a password: the app runs on the person's own computer.
import { arr, bool, obj, str, strings } from './decode'

export interface AppUser { name: string; active: boolean; roles: string[]; created_by: string; created_at: string }
export interface UsersList {
  note: string
  roles: string[]
  users: AppUser[]
  /** For each phase, the roles that may approve it right now. */
  approvers: Record<string, string[]>
  /** The same, before anyone changed it. */
  defaults: Record<string, string[]>
  /** Nobody is on the list yet, so nothing is restricted. */
  empty: boolean
  empty_hint: string
}
/** What the typed name may do. `why_not` has the server's own sentence for each phase it may NOT approve. */
export interface Me { name: string; on_list: boolean; roles: string[]; administrator: boolean; list_in_force: boolean; may_approve: string[]; why_not: Record<string, string> }

function listsByKey(value: unknown, w: string): Record<string, string[]> {
  const o = obj(value, w)
  return Object.fromEntries(Object.keys(o).map((k) => [k, strings(o[k], `${w}.${k}`)]))
}

export function decodeUser(value: unknown, w = 'user'): AppUser {
  const o = obj(value, w)
  return { name: str(o.name, `${w}.name`), active: bool(o.active, `${w}.active`), roles: strings(o.roles, `${w}.roles`), created_by: str(o.created_by, `${w}.created_by`), created_at: str(o.created_at, `${w}.created_at`) }
}

export function decodeUsersList(value: unknown): UsersList {
  const o = obj(value, 'users')
  return {
    note: str(o.note, 'users.note'), roles: strings(o.roles, 'users.roles'), users: arr(o.users, 'users.users').map((u, i) => decodeUser(u, `users.users[${i}]`)),
    approvers: listsByKey(o.approvers, 'users.approvers'), defaults: listsByKey(o.defaults, 'users.defaults'), empty: bool(o.empty, 'users.empty'), empty_hint: str(o.empty_hint, 'users.empty_hint'),
  }
}

export function decodeMe(value: unknown): Me {
  const o = obj(value, 'me')
  const why = obj(o.why_not, 'me.why_not')
  return {
    name: str(o.name, 'me.name'), on_list: bool(o.on_list, 'me.on_list'), roles: strings(o.roles, 'me.roles'), administrator: bool(o.administrator, 'me.administrator'),
    list_in_force: bool(o.list_in_force, 'me.list_in_force'), may_approve: strings(o.may_approve, 'me.may_approve'),
    why_not: Object.fromEntries(Object.keys(why).map((k) => [k, str(why[k], `me.why_not.${k}`)])),
  }
}

export function decodeApprovers(value: unknown): { phase: string; roles: string[] } {
  const o = obj(value, 'approvers')
  return { phase: str(o.phase, 'approvers.phase'), roles: strings(o.roles, 'approvers.roles') }
}
