// What the Templates tab needs, as plain functions so they are tested without a browser (S23 Part C).
import type { TemplateInfo, TemplatesView } from '../api/templates'

/** Only a name that ends .docx can be a template. The server checks the file itself; this only saves a trip for an obvious mistake. */
export const looksLikeDocx = (name: string): boolean => /\.docx$/i.test(name.trim())

/** The sentence under the choose-a-file button when the chosen file is plainly wrong, or null when it looks fine. */
export function fileProblem(file: { name: string; size: number } | null, maxMb: number): string | null {
  if (!file) return null
  if (!looksLikeDocx(file.name)) return 'A template must be a Word document with a name ending .docx.'
  if (file.size === 0) return 'That file is empty.'
  if (file.size > maxMb * 1024 * 1024) return `That file is larger than the ${maxMb} MB limit for a template.`
  return null
}

/** How big a stored template is, in words a person reads. */
export function sizeWords(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** "2026-11-05T10:00:00Z" -> "5 Nov 2026"; anything else is shown as given, never as "Invalid Date". */
export function whenWords(iso: string): string {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  return new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

/** How many of the document types have a template, and how many of those will be used (they have a table of contents). */
export function summary(view: Pick<TemplatesView, 'categories'>): { total: number; have: number; usable: number } {
  const have = view.categories.filter((c) => c.template)
  return { total: view.categories.length, have: have.length, usable: have.filter((c) => c.template!.has_toc).length }
}

export function summaryWords(view: Pick<TemplatesView, 'categories'>): string {
  const s = summary(view)
  if (s.have === 0) return 'No templates yet. Documents use the standard layout.'
  return `${s.have} of ${s.total} document types have a template; ${s.usable} will be used (the others have no table of contents).`
}

/** Can this person change templates right now: they may, a project is not archived, and nothing is already being sent. */
export const canChange = (view: Pick<TemplatesView, 'can_change'>, busy: boolean): boolean => view.can_change && !busy

/** The line shown to someone who may only read. */
export const readOnlyNotice = (view: Pick<TemplatesView, 'can_change'>): string | null =>
  view.can_change ? null : 'Only a Project Manager or an Administrator can change templates. You can read and download them.'

/** The address that downloads the stored original of a template. */
export const downloadPath = (projectId: string, category: string): string =>
  `/api/projects/${encodeURIComponent(projectId)}/templates/${encodeURIComponent(category)}/download`

/** After an upload: the sentence that says what was stored and whether it will be used. */
export function savedSentence(info: TemplateInfo): string {
  return `${info.label} template stored. ${info.toc_note}`
}

/** Read a project's templates AS THIS PERSON: the typed name goes with the read, because whether they may change anything depends on who they are, and the list is THIS project's. */
export const loadTemplates = (client: { templates(projectId: string, actor?: string): Promise<TemplatesView> }, projectId: string, actor: string): Promise<TemplatesView> => client.templates(projectId, actor)

/** What choosing a file does: the problem to show (or null), and the file to send (or null). A file with a plain problem is never sent. */
export function pick(file: { name: string; size: number } | null, maxMb: number): { problem: string | null; send: boolean } {
  const problem = fileProblem(file, maxMb)
  return { problem, send: !!file && !problem }
}

/** The callbacks of one document type's controls: its picker uploads to THAT type under the file's own name, and its Remove removes THAT type. */
export const uploadFor = (onUpload: (category: string, file: File, filename: string) => void, category: string) => (file: File) => onUpload(category, file, file.name)
export const removeFor = (onRemove: (category: string) => void, category: string) => () => onRemove(category)

/** One change (an upload or a removal): busy while it runs, the new view shown after, the server's own sentence kept when it is refused. Plain, so a test can follow every step. */
export async function runTemplateChange(
  what: () => Promise<TemplatesView>,
  ui: { setBusy: (b: boolean) => void; setError: (m: string | null) => void; setView: (v: TemplatesView) => void },
): Promise<void> {
  ui.setBusy(true); ui.setError(null)
  try { ui.setView(await what()) } catch (e) { ui.setError(e instanceof Error ? e.message : 'That could not be done.') } finally { ui.setBusy(false) }
}

/** The calls the tab makes, as functions of the client and the typed name, so each can be tested with a fake client. */
export interface TemplateCalls {
  uploadTemplate(projectId: string, category: string, file: File | Blob, filename: string, actor: string): Promise<TemplatesView>
  removeTemplate(projectId: string, category: string, actor: string): Promise<TemplatesView>
}
export function templateActions(client: TemplateCalls, projectId: string, actor: string) {
  return {
    upload: (category: string, file: File | Blob, filename: string) => client.uploadTemplate(projectId, category, file, filename, actor),
    remove: (category: string) => client.removeTemplate(projectId, category, actor),
  }
}
