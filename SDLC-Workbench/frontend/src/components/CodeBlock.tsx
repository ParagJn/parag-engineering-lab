import { Download } from 'lucide-react'
import { downloadName, extensionFor, lineCount } from '../lib/codeFiles'
import { saveText } from '../lib/download'

/**
 * A block of code in an artefact, shown as TEXT and collapsed until opened. It is a native <details>, so it opens and closes with no script and a reader
 * with scripts off still gets the code. The Download button saves exactly the text shown, in the file's own format (.sql, .py, .js ... or .txt).
 */
export function CodeBlock({ code, language, path, children }: { code: string; language: string | null; path: string | null; children: React.ReactNode }) {
  const name = downloadName(path, language)
  const lines = lineCount(code)
  return (
    <details className="code-block my-3 rounded-lg border border-slate-200 bg-white">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-3 py-2 text-sm">
        <span className="font-mono text-xs font-semibold">{path ?? `${language || 'code'} block`}</span>
        <span className="text-xs text-slate-500">{lines} {lines === 1 ? 'line' : 'lines'} · .{extensionFor(language, path)}</span>
      </summary>
      <div className="border-t border-slate-200 px-3 pb-3 pt-2">
        <button type="button" onClick={() => saveText(name, code)} aria-label={`Download ${name}`}
          className="mb-2 inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
          <Download size={12} aria-hidden /> Download {name}
        </button>
        {children}
      </div>
    </details>
  )
}
