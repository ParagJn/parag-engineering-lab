// The Build instruction set as the server saves it (S19): an overview and a list of files, then each file after a line `=== FILE: <name> ===`.
// This cuts the saved text into its parts so the reader can show each file folded and download it on its own. It is the twin of the server's
// `split_set` and reads the same marks; everything here is plain text in, plain text out, and nothing in a file is ever run.

import type { Finding, Severity } from '../api'

export const INSTRUCTION_KEY = 'build_instructions'

const MARK = /^=== FILE: (\S+) ===[ \t]*$/
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,78}\.md$/

export interface InstructionFile {
  /** The name the server gave the file, as written in the mark. */
  name: string
  /** The file's text, without its mark line and without blank lines at either end, ending in one newline (as the server's `split_set` returns it). */
  text: string
}

export interface InstructionSet {
  /** Everything before the first file: the overview, the list of files, the coverage check. */
  head: string
  files: InstructionFile[]
}

export function isInstructionSet(type: string): boolean {
  return type === INSTRUCTION_KEY
}

/** Cut a saved set into its head and its files. Never throws. A file named twice keeps its first text; text before the first mark is the head. */
export function splitInstructionSet(body: string): InstructionSet {
  const lines = (body ?? '').replace(/\r\n/g, '\n').split('\n')
  const head: string[] = []
  const files: InstructionFile[] = []
  const seen = new Set<string>()
  let current: { name: string; lines: string[]; keep: boolean } | null = null
  const close = () => {
    if (current && current.keep) files.push({ name: current.name, text: current.lines.join('\n').replace(/^\n+|\n+$/g, '') + '\n' })
  }
  for (const line of lines) {
    const mark = MARK.exec(line)
    if (mark) {
      close()
      const keep = !seen.has(mark[1])
      seen.add(mark[1])
      current = { name: mark[1], lines: [], keep }
    } else if (current) current.lines.push(line)
    else head.push(line)
  }
  close()
  return { head: head.join('\n').replace(/\n+$/, ''), files }
}

/** The name a file is saved under on the person's machine: its own name when that is a plain `.md` name, otherwise a safe name made from it. */
export function instructionDownloadName(name: string): string {
  if (SAFE_NAME.test(name)) return name
  const stem = name.replace(/\.md$/i, '').replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[._-]+/, '').slice(0, 70)
  return `${stem || 'instructions'}.md`
}

/** What a file's Download button saves: the name it is saved under and exactly the file's own text. */
export function downloadOf(file: InstructionFile): { name: string; text: string } {
  return { name: instructionDownloadName(file.name), text: file.text }
}

export function lineCountOf(text: string): number {
  if (!text) return 0
  return text.endsWith('\n') ? text.split('\n').length - 1 : text.split('\n').length
}

// ---- a review of the set, shown file by file ----------------------------------------------------------------------------------------------------------

const FILE_TARGET = /^([A-Za-z0-9][A-Za-z0-9._-]*\.md)(?::(\d{1,5}))?$/
const RANK: Record<Severity, number> = { high: 3, medium: 2, low: 1 }

export interface FileFindings { findings: Finding[]; worst: Severity }

/** The text of one file of a saved set, as the server's `split_set` holds it (so an unchanged box saves nothing). Empty when the set has no such file. */
export function fileText(body: string, name: string): string {
  return splitInstructionSet(body).files.find((f) => f.name === name)?.text ?? ''
}

/** The design index is written by the system from the other files; everything else in a set can be edited by hand, one file at a time. */
export function canEditFile(name: string): boolean {
  return name !== '02-design-index.md'
}

/** Which file a finding is about, and the line if it names one. A finding about the set as a whole (`General`) has no file. */
export function fileOfTarget(target: string): { file: string; line: number | null } | null {
  const m = FILE_TARGET.exec(target)
  return m ? { file: m[1], line: m[2] === undefined ? null : Number(m[2]) } : null
}

/** A review's findings grouped by the file they name (in the order they came), and the ones that name no file. The page decides nothing: the server already checked each target. */
export function groupByFile(findings: readonly Finding[]): { byFile: Map<string, FileFindings>; general: Finding[]; unplaced: Finding[] } {
  const byFile = new Map<string, FileFindings>()
  const general: Finding[] = []
  const unplaced: Finding[] = []
  for (const f of findings) {
    if (f.target === 'General') { general.push(f); continue }
    const at = fileOfTarget(f.target)
    if (at === null) { unplaced.push(f); continue }
    const have = byFile.get(at.file)
    byFile.set(at.file, { findings: [...(have?.findings ?? []), f], worst: have && RANK[have.worst] >= RANK[f.severity] ? have.worst : f.severity })
  }
  return { byFile, general, unplaced }
}

/** The files a review names that are not in the set it is shown beside (an older review of a different version). Their findings are listed, not lost. */
export function strayFiles(byFile: Map<string, FileFindings>, files: readonly InstructionFile[]): string[] {
  const have = new Set(files.map((f) => f.name))
  return [...byFile.keys()].filter((name) => !have.has(name))
}

/** The lines of a text as a review numbers them: line 1 is the first, and the empty piece after a final newline is not a line. */
export function linesOf(text: string): string[] {
  const parts = (text ?? '').replace(/\r\n/g, '\n').split('\n')
  if (parts.length > 1 && parts[parts.length - 1] === '') parts.pop()
  return parts
}

/** What a download from the run panel saves, worked out from the saved set. `file` is one file's name, or null for every file. One file is saved as its own `.md`; every
 *  file is saved together as one zip named after the artefact and its version. Returns null when the set has no such file. */
export type DownloadPlan =
  | { kind: 'file'; name: string; text: string }
  | { kind: 'zip'; name: string; entries: { name: string; text: string }[] }

export function planDownload(body: string, file: string | null, artefactId: string, version: number): DownloadPlan | null {
  const { files } = splitInstructionSet(body)
  if (file !== null) {
    const one = files.find((f) => f.name === file)
    return one ? { kind: 'file', ...downloadOf(one) } : null
  }
  if (files.length === 0) return null
  return { kind: 'zip', name: `${artefactId.replace(/[^A-Za-z0-9._-]+/g, '_')}-v${version}.zip`, entries: files.map((f) => downloadOf(f)) }
}
