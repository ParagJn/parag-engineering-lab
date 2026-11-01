// Small rules about documents that the screen can check before a round trip. The server checks again and has the last word.
export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const MAX_STAGED = 10
export const EXTENSIONS = ['txt', 'md', 'markdown', 'docx', 'pdf'] as const

/** A document chosen in the wizard before the project exists. It is uploaded as soon as the project has been created. */
export interface StagedDocument { key: string; filename: string; size: number; blob: Blob }

/** A file name for pasted text: no folders, no control characters, a readable extension (`.md` unless it already ends `.txt` or `.md`). */
export function pastedFilename(raw: string): string {
  const base = raw.replace(/[\u0000-\u001f\u007f]/g, ' ').split(/[\\/]/).pop() ?? ''
  const cleaned = base.split(/\s+/).filter(Boolean).join(' ').slice(0, 100)
  const name = cleaned.replace(/^\.+/, '') || 'pasted-notes'
  return /\.(md|markdown|txt)$/i.test(name) ? name : `${name}.md`
}

export function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot < 0 ? '' : filename.slice(dot + 1).toLowerCase()
}

/** Why a file cannot be added, in a sentence, or null. `already` is how many are staged already. */
export function fileProblem(filename: string, size: number, already: number): string | null {
  if (!EXTENSIONS.includes(extensionOf(filename) as (typeof EXTENSIONS)[number])) {
    return `“${filename}” is not a supported file type; use ${EXTENSIONS.map((e) => '.' + e).join(', ')}.`
  }
  if (size === 0) return `“${filename}” is empty.`
  if (size > MAX_FILE_BYTES) return `“${filename}” is larger than the ${MAX_FILE_BYTES / (1024 * 1024)} MB limit.`
  if (already >= MAX_STAGED) return `Add up to ${MAX_STAGED} documents here; the rest can be added on the project page.`
  return null
}

/** Pasted text with nothing in it is not a document. */
export function pasteProblem(text: string): string | null {
  return text.trim() ? null : 'Paste some text first.'
}
