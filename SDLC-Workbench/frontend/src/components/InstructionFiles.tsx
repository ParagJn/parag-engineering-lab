import { Download, Pencil } from 'lucide-react'
import type { Finding } from '../api'
import { count } from '../lib/format'
import { saveText } from '../lib/download'
import { canEditFile, downloadOf, groupByFile, lineCountOf, splitInstructionSet } from '../lib/instructionSet'
import { FindingRow } from './ReviewPanel'
import { SafeMarkdown } from './SafeMarkdown'

const CHIP = { high: 'border-rose-300 bg-rose-50 text-rose-800', medium: 'border-amber-300 bg-amber-50 text-amber-900', low: 'border-sky-300 bg-sky-50 text-sky-800' } as const

/**
 * The Build instruction set (S19): the overview and file list as text, then every file FOLDED. Each file is a native <details> (it opens and closes with no script,
 * and starts closed every time the page is opened or refreshed), and has its own Download button that saves exactly the file's text as its own .md.
 * Inside an opened file every code block (the acceptance tests are 28 of them) is folded too, each with its own download.
 *
 * With a review of THIS version (`findings`), each file shows how many findings it has, in the colour of the worst, and lists them at the top of the fold, each with the line it
 * names. (The usual colour marks on an artefact's own text look for item IDs and headings; a finding about a file has neither, so it is shown here instead.)
 */
export function InstructionFiles({ body, findings = [], onEditFile }: { body: string; findings?: readonly Finding[]; onEditFile?: (name: string) => void }) {
  const { head, files } = splitInstructionSet(body)
  const { byFile } = groupByFile(findings)
  return (
    <div>
      {head.trim() && <SafeMarkdown>{head}</SafeMarkdown>}
      {files.length === 0 && <p className="mt-3 text-sm text-slate-500">This version holds no files.</p>}
      <ul aria-label="Instruction files" className="mt-2 list-none space-y-2 p-0">
        {files.map((f) => {
          const saveAs = downloadOf(f).name
          const lines = lineCountOf(f.text)
          const here = byFile.get(f.name)
          return (
            <li key={f.name}>
              <details className="rounded-lg border border-slate-200 bg-white">
                <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="font-mono text-xs font-semibold">{f.name}</span>
                  <span className="text-xs text-slate-500">{count(lines, 'line')}</span>
                  {here && <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${CHIP[here.worst]}`}>{count(here.findings.length, 'finding')}</span>}
                </summary>
                <div className="border-t border-slate-200 px-3 pb-3 pt-2">
                  {here && (
                    <ul aria-label={`Findings for ${f.name}`} className="mb-3 list-none space-y-2 p-0">
                      {here.findings.map((x, i) => <FindingRow key={i} finding={x} />)}
                    </ul>
                  )}
                  {onEditFile && canEditFile(f.name) && (
                    <button type="button" onClick={() => onEditFile(f.name)} aria-label={`Edit ${f.name}`}
                      className="mb-2 mr-2 inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                      <Pencil size={12} aria-hidden /> Edit this file
                    </button>
                  )}
                  <button type="button" onClick={() => { const d = downloadOf(f); saveText(d.name, d.text) }} aria-label={`Download ${saveAs}`}
                    className="mb-2 inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                    <Download size={12} aria-hidden /> Download {saveAs}
                  </button>
                  <SafeMarkdown collapseCode>{f.text}</SafeMarkdown>
                </div>
              </details>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
