// How code in an artefact is presented (S18): which blocks are files, what each one is called, and the format it is downloaded in.
// Everything here is plain text in, plain text out. Code is shown and saved as TEXT; nothing in this file ever runs or interprets it.

/** The Build artefacts whose body is code. The same four the server writes into a project's workspace. */
export const CODE_ARTEFACT_TYPES = ['database_schema', 'backend_code', 'frontend_code', 'test_suite'] as const

export function isCodeArtefact(type: string): boolean {
  return (CODE_ARTEFACT_TYPES as readonly string[]).includes(type)
}

/** The one sentence shown wherever generated code is shown. It is the same everywhere, on purpose, and says plainly what the code is NOT. */
export const PROTOTYPE_NOTICE = {
  title: 'Prototype code',
  text: 'Generated to show the idea and to be tried out. It is not production code: have production code written and reviewed outside this tool.',
} as const

/** The file type a download gets, by the language the code block says it is, then by the file name it was given. Anything else is plain text. */
const BY_LANGUAGE: Record<string, string> = {
  sql: 'sql', python: 'py', py: 'py', javascript: 'js', js: 'js', typescript: 'ts', ts: 'ts', html: 'html', css: 'css', json: 'json',
  yaml: 'yml', yml: 'yml', markdown: 'md', md: 'md', bash: 'sh', sh: 'sh', shell: 'sh', xml: 'xml', toml: 'toml', ini: 'ini',
}
const KNOWN_EXTENSIONS = new Set(Object.values(BY_LANGUAGE))

export function extensionFor(language: string | null, path: string | null): string {
  if (path) {
    const dot = path.lastIndexOf('.')
    const ext = dot > 0 && dot < path.length - 1 ? path.slice(dot + 1).toLowerCase() : ''
    if (KNOWN_EXTENSIONS.has(ext)) return ext
  }
  const key = (language ?? '').trim().toLowerCase()
  return BY_LANGUAGE[key] ?? 'txt'
}

/** The file name a download is saved as: the last part of the path with its own type, or a name from the language when the block had no file name. */
export function downloadName(path: string | null, language: string | null, fallback = 'code'): string {
  const ext = extensionFor(language, path)
  if (!path) return `${fallback}.${ext}`
  const last = path.split('/').filter(Boolean).pop() ?? fallback
  const dot = last.lastIndexOf('.')
  const stem = dot > 0 ? last.slice(0, dot) : last
  const safe = (stem.replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^\.+/, '') || fallback)
  return `${safe}.${ext}`
}

export function lineCount(text: string): number {
  if (!text) return 0
  return text.endsWith('\n') ? text.split('\n').length - 1 : text.split('\n').length
}

/** The file name the artefact's own `File: <path>` line gave the block, found from the text just before it. Null when the block had none. */
const FILE_LINE = /^\s{0,3}(?:#{1,6}[ \t]+)?(?:[-*][ \t]+)?(?:\*\*|__)?File:[ \t]*(?:\*\*|__)?[ \t]*`?([^`\s*]+)`?(?:\*\*|__)?[ \t]*$/

export function filePathBefore(markdown: string, blockStartLine: number): string | null {
  const lines = markdown.split('\n')
  for (let i = blockStartLine - 2; i >= 0 && i >= blockStartLine - 3; i -= 1) {
    const line = lines[i] ?? ''
    if (!line.trim()) continue
    const match = FILE_LINE.exec(line)
    return match ? match[1] : null
  }
  return null
}
