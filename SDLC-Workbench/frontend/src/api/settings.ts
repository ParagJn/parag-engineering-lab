// System settings (S23d, S23e): what the app's settings are, which are secrets (never shown), and saving a change. The server decides everything, including what is valid; the screen shows it.
import { arr, bool, obj, str, strings } from './decode'

export const KINDS = ['text', 'number', 'whole', 'yes_no', 'choice', 'secret'] as const
export type SettingKind = (typeof KINDS)[number]

/** One setting. A secret has `is_set` and never a value; any other has its `value` as text, its `default` and whether it `changed`. */
export interface SettingEntry {
  key: string; env_name: string; group: string; label: string; help: string; kind: SettingKind; unit: string; choices: string[]; secret: boolean
  is_set?: boolean; value?: string; default?: string; changed?: boolean
}
export interface SettingsGroup { key: string; title: string; help: string; settings: SettingEntry[] }
export interface BackupInfo { name: string; size: number }
export interface SettingsView {
  groups: SettingsGroup[]; restart_pending: boolean; can_edit: boolean; editable: boolean; note: string; restart_sentence: string; backups: BackupInfo[]
  /** Present on the answer to a save or a restore. */
  saved?: { changed: string[]; backup: string; message: string }
}

export function decodeSettingEntry(value: unknown, w = 'setting'): SettingEntry {
  const o = obj(value, w)
  const kind = str(o.kind, `${w}.kind`)
  if (!(KINDS as readonly string[]).includes(kind)) throw new Error(`${w}.kind: unknown kind`)
  const secret = bool(o.secret, `${w}.secret`)
  const entry: SettingEntry = {
    key: str(o.key, `${w}.key`), env_name: str(o.env_name, `${w}.env_name`), group: str(o.group, `${w}.group`), label: str(o.label, `${w}.label`), help: str(o.help, `${w}.help`),
    kind: kind as SettingKind, unit: str(o.unit, `${w}.unit`), choices: strings(o.choices, `${w}.choices`), secret,
  }
  if (secret) entry.is_set = bool(o.is_set, `${w}.is_set`)
  else { entry.value = str(o.value, `${w}.value`); entry.default = str(o.default, `${w}.default`); entry.changed = bool(o.changed, `${w}.changed`) }
  return entry
}

export function decodeSettings(value: unknown): SettingsView {
  const o = obj(value, 'settings')
  const view: SettingsView = {
    groups: arr(o.groups, 'settings.groups').map((g, i) => {
      const go = obj(g, `settings.groups[${i}]`)
      return { key: str(go.key, `settings.groups[${i}].key`), title: str(go.title, `settings.groups[${i}].title`), help: str(go.help, `settings.groups[${i}].help`),
               settings: arr(go.settings, `settings.groups[${i}].settings`).map((s, j) => decodeSettingEntry(s, `settings.groups[${i}].settings[${j}]`)) }
    }),
    restart_pending: bool(o.restart_pending, 'settings.restart_pending'), can_edit: bool(o.can_edit, 'settings.can_edit'), editable: bool(o.editable, 'settings.editable'),
    note: str(o.note, 'settings.note'), restart_sentence: str(o.restart_sentence, 'settings.restart_sentence'),
    backups: arr(o.backups, 'settings.backups').map((b, i) => { const bo = obj(b, `settings.backups[${i}]`); return { name: str(bo.name, `settings.backups[${i}].name`), size: Number(bo.size) } }),
  }
  if ('saved' in o) {
    const s = obj(o.saved, 'settings.saved')
    view.saved = { changed: strings(s.changed, 'settings.saved.changed'), backup: str(s.backup, 'settings.saved.backup'), message: str(s.message, 'settings.saved.message') }
  }
  return view
}
