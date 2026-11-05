// What the System settings tab needs, as plain functions so they are tested without a browser (S23).
import type { SettingEntry, SettingsView } from '../api/settings'

/** What a person has typed so far: a key to the text in its box. A setting that has no entry here has not been touched. */
export type Draft = Record<string, string>

/** The value the box starts with. A secret's box starts EMPTY: its value is never sent to the screen. */
export const startValue = (s: SettingEntry): string => (s.secret ? '' : (s.value ?? ''))

/** The current text of a setting's box: what was typed, else where it started. */
export const boxValue = (s: SettingEntry, draft: Draft): string => (s.key in draft ? draft[s.key] : startValue(s))

/** Has this box been changed from where it started? A secret counts as changed once anything is typed (a blank secret means "keep it"). */
export function isEdited(s: SettingEntry, draft: Draft): boolean {
  if (!(s.key in draft)) return false
  return s.secret ? draft[s.key].trim() !== '' : draft[s.key] !== startValue(s)
}

/** Only the boxes that were really changed: this is exactly what is sent, so an untouched setting is never rewritten. */
export function changes(view: Pick<SettingsView, 'groups'>, draft: Draft): Record<string, string> {
  const out: Record<string, string> = {}
  for (const g of view.groups) for (const s of g.settings) if (isEdited(s, draft)) out[s.key] = draft[s.key]
  return out
}

export const editedCount = (view: Pick<SettingsView, 'groups'>, draft: Draft): number => Object.keys(changes(view, draft)).length

/** Put one box back to where it started. */
export function reset(draft: Draft, key: string): Draft {
  const { [key]: _gone, ...rest } = draft
  return rest
}

/** Can the Save button be pressed? Something was changed, the person may save, and nothing is being saved already. */
export const canSave = (view: Pick<SettingsView, 'groups' | 'can_edit' | 'editable'>, draft: Draft, busy: boolean): boolean =>
  view.can_edit && view.editable && !busy && editedCount(view, draft) > 0

/** The line under the heading that says what the person can do here. */
export function editNotice(view: Pick<SettingsView, 'can_edit' | 'editable'>): string | null {
  if (!view.editable) return 'This app was started with settings given to it, so they cannot be changed here. You can read them.'
  if (!view.can_edit) return 'Only an Administrator can change settings. You can read them.'
  return null
}

/** The banner shown while a saved change is waiting for the app to be restarted. */
export const restartBanner = (view: Pick<SettingsView, 'restart_pending' | 'restart_sentence'>): string | null => (view.restart_pending ? view.restart_sentence : null)

/** The words for a secret: only whether it is set. */
export const secretWords = (s: SettingEntry): string => (s.is_set ? 'Set' : 'Not set')

/** How a value reads beside its default: nothing for an unchanged setting, "default: x" for a changed one. */
export function defaultNote(s: SettingEntry): string | null {
  if (s.secret || !s.changed) return null
  return `Default: ${s.default === '' ? 'blank' : s.default}${s.unit ? ' ' + s.unit : ''}`
}

/** The settings of a group whose value is not the default: how many, for the group's heading. */
export const changedIn = (settings: readonly SettingEntry[]): number => settings.filter((s) => !s.secret && s.changed).length

/** What to say after a save: the server's sentence, with the names of what changed. */
export function savedSentence(saved: NonNullable<SettingsView['saved']>): string {
  return saved.changed.length === 0 ? saved.message : `${saved.message} Changed: ${saved.changed.join(', ')}.`
}

/** Read the settings AS THIS PERSON: the typed name goes with the read, because whether they may change anything depends on who they are. Plain, so a test can see the name is sent. */
export const loadSettings = (client: { settings(actor?: string): Promise<SettingsView> }, actor: string): Promise<SettingsView> => client.settings(actor)

/** The change a typed box makes to the draft: exactly that setting, nothing else. */
export const typed = (draft: Draft, key: string, value: string): Draft => ({ ...draft, [key]: value })

/** What a save and a restore call: only the changed boxes, in the typed name; a restore names the version. Plain, so a test can check what is sent. */
export function settingsCalls(client: { saveSettings(a: string, v: Record<string, string>): Promise<SettingsView>; restoreSettings(a: string, n: string): Promise<SettingsView> }, actor: string, view: Pick<SettingsView, 'groups'>, draft: Draft) {
  return { save: () => client.saveSettings(actor, changes(view, draft)), restore: (name: string) => client.restoreSettings(actor, name) }
}

/** The input element type for a kind. A secret box hides what is typed. */
export const inputType = (s: SettingEntry): 'text' | 'password' | 'number' => (s.kind === 'secret' ? 'password' : 'text')

/** The pieces of a refusal to show: the server's headline, and the list of variables with their sentences when it gave one. */
export function refusalParts(e: unknown): { message: string; problems: string[] } {
  const problems = typeof e === 'object' && e !== null && Array.isArray((e as { problems?: unknown }).problems) ? ((e as { problems: unknown[] }).problems).map(String) : []
  return { message: e instanceof Error ? e.message : 'That could not be saved.', problems }
}

/** One save: busy while it runs; on success the new view replaces the old one and the draft is cleared; on a refusal the draft is KEPT (nothing the person typed is lost) and the server's
 *  sentences are shown. Plain, so a test can follow every step. */
export async function runSave(
  what: () => Promise<SettingsView>,
  ui: { setBusy: (b: boolean) => void; setError: (m: string | null, problems: string[]) => void; setView: (v: SettingsView) => void; clearDraft: () => void },
): Promise<void> {
  ui.setBusy(true); ui.setError(null, [])
  try { const view = await what(); ui.setView(view); ui.clearDraft() } catch (e) { const r = refusalParts(e); ui.setError(r.message, r.problems) } finally { ui.setBusy(false) }
}
