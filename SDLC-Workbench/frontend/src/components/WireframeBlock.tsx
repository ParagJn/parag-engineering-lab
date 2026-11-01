import { sanitiseSvg } from '../lib/svg'
import { Notice } from './Notice'

/** The data address a cleaned drawing is shown from. Exported so a test can read back exactly what would be drawn. */
export function drawingAddress(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

/** What a drawing's title says, for the picture's alternative text: "LFS-001 Room list". */
export function drawingTitle(svg: string): string {
  const match = /<title>([^<]*)<\/title>/.exec(svg)
  if (!match) return 'A wireframe'
  // The cleaned drawing holds its text escaped; the alternative text should read as the model wrote it. (React escapes it again on the way out.)
  const text = match[1].replace(/&(amp|lt|gt|quot|apos);/g, (_m, name: string) => ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" })[name] as string)
  return text.trim() || 'A wireframe'
}

/**
 * A wireframe, drawn. Two layers, on purpose:
 *   1. the drawing is cleaned here, in the browser, by the allow-list sanitiser (the server already cleaned it once; this does not trust that), and
 *   2. what is left is shown as an IMAGE from a data address, not placed in the page, so a browser never runs a script in it even if layer 1 had a gap.
 * The source is one click away, as text.
 */
export function WireframeBlock({ source }: { source: string }) {
  const cleaned = sanitiseSvg(source)
  return (
    <figure className="my-3 rounded-xl border border-slate-200 bg-white p-3">
      {cleaned.ok ? (
        <img src={drawingAddress(cleaned.svg)} alt={drawingTitle(cleaned.svg)} className="mx-auto block h-auto max-w-full rounded border border-slate-100 bg-white" loading="lazy" />
      ) : (
        <Notice tone="warn" title="This drawing cannot be shown">{cleaned.removed.length ? cleaned.removed.join('; ') : 'It is not a drawing.'}</Notice>
      )}
      {cleaned.ok && cleaned.changed && (
        <p className="mt-2 text-xs text-amber-800">Parts of this drawing were left out for safety: {cleaned.removed.join('; ')}.</p>
      )}
      <details className="mt-2 text-xs text-slate-600">
        <summary className="cursor-pointer">Show source</summary>
        <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-2 font-mono">{source}</pre>
      </details>
    </figure>
  )
}
