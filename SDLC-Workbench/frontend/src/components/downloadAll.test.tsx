// Downloading the files of the Build instruction set from the run panel (one file, or all as a zip). Static renders plus the plain function that does the work.
import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { saveBytes } from '../lib/download'
import { applyEvent, idle, type Progress } from '../state/runProgress'
import { downloadSetFiles } from '../state/useProjectScreen'
import { planDownload } from '../lib/instructionSet'
import { RunPanel } from './RunPanel'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const e = (id: number, type: string, data: Record<string, unknown>) => ({ id, type, run_id: 'r', at: 't', ...data }) as never
const lead = [e(1, 'run.started', { phase: 'build', artefacts: ['build_instructions', 'personas'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 }), e(2, 'artefact.started', { key: 'build_instructions' })]
const piece = (n: number, file: string) => [e(10 + n, 'piece.started', { key: 'build_instructions', file, stage: 'use_case', index: n, of: 2 }), e(20 + n, 'piece.finished', { key: 'build_instructions', file, attempts: 1, tokens_in: 1, tokens_out: 1, cost_usd: 0.01 })]
const finished = (id = 'BLD-INS-001', version = 2) => e(40, 'artefact.finished', { key: 'build_instructions', artefact_id: id, version, attempts: 1, cost_usd: 0.02, items: 2, flags: 0, author: 'agent:x@m' })
const progress = (events: unknown[]): Progress => (events as never[]).reduce((p: Progress, ev) => applyEvent(p, ev), idle)
const done = progress([...lead, ...piece(1, '00-foundation.md'), ...piece(2, 'UC-001-a.md'), finished(),
  e(50, 'artefact.started', { key: 'personas' }), e(51, 'artefact.finished', { key: 'personas', artefact_id: 'REQ-PER-001', version: 1, attempts: 1, cost_usd: 0.01, items: 1, flags: 0, author: 'agent:x@m' })])
const props = { names: { build_instructions: 'Build instructions', personas: 'Personas' }, connected: true, cancelling: false, cancelNote: null, problem: null, onCancel: noop, onOpen: noop }

type El = ReactElement<{ children?: ReactNode; onClick?: () => void; 'aria-label'?: string }>
function find(node: ReactNode, test: (e: El) => boolean, out: El[] = []): El[] {
  if (Array.isArray(node)) { node.forEach((n) => find(n, test, out)); return out }
  if (node && typeof node === 'object' && 'props' in node) { const el = node as El; if (test(el)) out.push(el); find(el.props.children, test, out) }
  return out
}
const labelled = (tree: ReactNode, prefix: string) => find(tree, (x) => x.type === 'button' && String(x.props['aria-label'] ?? '').startsWith(prefix))

describe('the buttons in the run panel', () => {
  it('a finished set has Download all (zip) next to Read it, and a Download beside each written file', () => {
    const out = html(<RunPanel {...props} progress={done} onDownload={noop} />)
    expect(out).toContain('Download all (zip)'); expect(out).toContain('aria-label="Download all files as a zip"')
    expect(out).toContain('aria-label="Download 00-foundation.md"'); expect(out).toContain('aria-label="Download UC-001-a.md"')
    expect(out.indexOf('Download all (zip)')).toBeLessThan(out.indexOf('Read it'))
  })
  it('the buttons beside the files are the icon alone, named for the file for a screen reader and on hover, with no word beside the icon', () => {
    const out = html(<RunPanel {...props} progress={done} onDownload={noop} />)
    const one = out.slice(out.indexOf('aria-label="Download 00-foundation.md"'), out.indexOf('</button>', out.indexOf('aria-label="Download 00-foundation.md"')))
    expect(one).toContain('title="Download 00-foundation.md"'); expect(one).toMatch(/<svg[^>]*aria-hidden="true"/)
    expect(one.slice(one.indexOf('</svg>') + 6)).toBe('')                                    // nothing after the icon: no word
    expect(out.match(/aria-label="Download (?!all)[^"]+\.md"/g)).toHaveLength(2)
  })
  it('an artefact that is not a set of files has Read it and nothing to download', () => {
    const out = html(<RunPanel {...props} progress={done} onDownload={noop} />)
    const personas = out.slice(out.indexOf('Personas'))
    expect(personas).toContain('Read it'); expect(personas).not.toContain('Download')
  })
  it('without a download handler there are no download buttons at all, and Read it keeps its place', () => {
    const out = html(<RunPanel {...props} progress={done} />)
    expect(out).not.toContain('Download'); expect(out).toContain('ml-auto text-xs underline">Read it')
  })
  it('while the set is still being written nothing can be downloaded, because the set is not saved until the last file is in', () => {
    const p = progress([...lead, ...piece(1, '00-foundation.md'), e(30, 'piece.started', { key: 'build_instructions', file: 'UC-001-a.md', stage: 'use_case', index: 2, of: 2 })])
    const out = html(<RunPanel {...props} progress={p} onDownload={noop} />)
    expect(out).not.toContain('Download')
    const bad = progress([...lead, e(30, 'piece.started', { key: 'build_instructions', file: 'a.md', stage: 'foundation', index: 1, of: 1 }), e(31, 'piece.failed', { key: 'build_instructions', file: 'a.md', reason: 'no' })])
    expect(html(<RunPanel {...props} progress={bad} onDownload={noop} />)).not.toContain('Download')
  })
  it('a file that failed has no Download even when the set it belongs to is saved, and the written ones do', () => {
    const p = progress([...lead, ...piece(1, '00-foundation.md'), e(30, 'piece.started', { key: 'build_instructions', file: 'UC-001-a.md', stage: 'use_case', index: 2, of: 2 }),
      e(31, 'piece.failed', { key: 'build_instructions', file: 'UC-001-a.md', reason: 'no' }), finished()])
    const out = html(<RunPanel {...props} progress={p} onDownload={noop} />)
    expect(out).toContain('aria-label="Download 00-foundation.md"'); expect(out).not.toContain('aria-label="Download UC-001-a.md"')
  })
  it('pressing Download all asks for every file of the version the run wrote, and a file asks for that file', () => {
    const asked: unknown[][] = []
    const tree = RunPanel({ ...props, progress: done, onDownload: (...a) => { asked.push(a) } })
    labelled(tree, 'Download all').forEach((b) => b.props.onClick!())
    expect(asked).toEqual([['BLD-INS-001', 2, null]])
    asked.length = 0
    const pieces = find(tree, (x) => typeof x.type === 'function' && (x.type as { name?: string }).name === 'Pieces')
    const rendered = (pieces[0].type as (p: unknown) => ReactElement)(pieces[0].props)
    labelled(rendered, 'Download ').forEach((b) => b.props.onClick!())
    expect(asked).toEqual([['BLD-INS-001', 2, '00-foundation.md'], ['BLD-INS-001', 2, 'UC-001-a.md']])
  })
  it('shows why nothing was saved, as text', () => {
    const out = html(<RunPanel {...props} progress={done} onDownload={noop} downloadNote="could not <b>fetch</b>" />)
    expect(out).toContain('Nothing was saved'); expect(out).toContain('could not &lt;b&gt;fetch&lt;/b&gt;')
    expect(html(<RunPanel {...props} progress={done} onDownload={noop} />)).not.toContain('Nothing was saved')
  })
})

const BODY = '## Overview\nx\n\n## Instructions\n=== FILE: 00-foundation.md ===\n# Foundation\n\n=== FILE: UC-001-a.md ===\n# A\n\n=== FILE: a+b.md ===\n# Odd\n'

describe('what a download saves', () => {
  it('one file is its own text under its own name; a name that is not safe is made safe', () => {
    expect(planDownload(BODY, '00-foundation.md', 'BLD-INS-001', 2)).toEqual({ kind: 'file', name: '00-foundation.md', text: '# Foundation\n' })
    expect(planDownload(BODY, 'a+b.md', 'BLD-INS-001', 2)).toMatchObject({ kind: 'file', name: 'a_b.md' })
  })
  it('all files are one zip named for the artefact and version, holding every file under the same names the single downloads use', () => {
    const plan = planDownload(BODY, null, 'BLD-INS-001', 2)
    expect(plan).toMatchObject({ kind: 'zip', name: 'BLD-INS-001-v2.zip' })
    expect(plan!.kind === 'zip' && plan!.entries.map((x) => x.name)).toEqual(['00-foundation.md', 'UC-001-a.md', 'a_b.md'])
    expect(plan!.kind === 'zip' && plan!.entries[1].text).toBe('# A\n')
  })
  it('a file that is not there, or a set with no files, gives nothing to save', () => {
    expect(planDownload(BODY, 'nope.md', 'A', 1)).toBeNull(); expect(planDownload('## Overview\nnothing\n', null, 'A', 1)).toBeNull(); expect(planDownload('## Overview\nnothing\n', 'a.md', 'A', 1)).toBeNull()
  })
  it('keeps an artefact id that has odd characters out of the zip\'s name', () => {
    expect(planDownload(BODY, null, 'A/../B C', 1)).toMatchObject({ name: 'A_.._B_C-v1.zip' })
  })
})

describe('saving the bytes of a zip', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('hands the browser the bytes themselves as a zip file, not their text', async () => {
    let made: Blob | null = null
    const click = vi.fn()
    vi.stubGlobal('document', { createElement: () => ({ click, set href(_v: string) {}, set download(_v: string) {} }), body: { appendChild: () => {}, removeChild: () => {} } })
    vi.stubGlobal('URL', { createObjectURL: (b: Blob) => { made = b; return 'blob:x' }, revokeObjectURL: () => {} })
    saveBytes('x.zip', new Uint8Array([0x50, 0x4b, 3, 4, 255, 0, 128]))
    expect(click).toHaveBeenCalledTimes(1); expect(made!.type).toBe('application/zip')
    expect(Array.from(new Uint8Array(await made!.arrayBuffer()))).toEqual([0x50, 0x4b, 3, 4, 255, 0, 128])
  })
})

describe('the note about a download that did not work', () => {
  it('is cleared the moment the next download starts, and set again only if that one fails', async () => {
    const { downloadFilesWith } = await import('../state/useProjectScreen')
    const notes: (string | null)[] = []
    const ok = vi.fn(async () => null), fail = vi.fn(async () => 'it broke')
    await downloadFilesWith((n) => notes.push(n), ok)
    await downloadFilesWith((n) => notes.push(n), fail)
    await downloadFilesWith((n) => notes.push(n), ok)
    expect(notes).toEqual([null, null, null, 'it broke', null, null])
  })
})

describe('downloadSetFiles', () => {
  const detail = { body: BODY, version: 2 }
  const fake = (get: () => Promise<unknown>) => { const getArtefact = vi.fn(get); return { client: { getArtefact } as never, getArtefact, text: vi.fn(), zip: vi.fn() } }
  it('fetches the version the run wrote, then saves one file as text', async () => {
    const f = fake(async () => detail)
    expect(await downloadSetFiles(f.client, { text: f.text, zip: f.zip }, 'p1', 'BLD-INS-001', 2, '00-foundation.md')).toBeNull()
    expect(f.getArtefact).toHaveBeenCalledWith('p1', 'BLD-INS-001', 2); expect(f.text).toHaveBeenCalledWith('00-foundation.md', '# Foundation\n'); expect(f.zip).not.toHaveBeenCalled()
  })
  it('saves every file as one zip that reads back with the same files', async () => {
    const f = fake(async () => detail)
    expect(await downloadSetFiles(f.client, { text: f.text, zip: f.zip }, 'p1', 'BLD-INS-001', null, null)).toBeNull()
    expect(f.getArtefact).toHaveBeenCalledWith('p1', 'BLD-INS-001', undefined); expect(f.text).not.toHaveBeenCalled()
    const [name, bytes] = f.zip.mock.calls[0]
    expect(name).toBe('BLD-INS-001-v2.zip'); expect(new TextDecoder().decode(bytes)).toContain('00-foundation.md'); expect(new TextDecoder().decode(bytes)).toContain('# A\n')
  })
  it('says so and saves nothing when the files could not be fetched, a file is gone, or the set is empty', async () => {
    const failed = fake(async () => { throw new Error('the backend is down') })
    expect(await downloadSetFiles(failed.client, { text: failed.text, zip: failed.zip }, 'p', 'A', 1, null)).toBe('the backend is down')
    const gone = fake(async () => detail)
    expect(await downloadSetFiles(gone.client, { text: gone.text, zip: gone.zip }, 'p', 'A', 1, 'nope.md')).toBe('nope.md is not in this version, so nothing was saved.')
    const empty = fake(async () => ({ body: '## Overview\nx\n', version: 1 }))
    expect(await downloadSetFiles(empty.client, { text: empty.text, zip: empty.zip }, 'p', 'A', 1, null)).toBe('This version holds no files, so there is nothing to save.')
    for (const f of [failed, gone, empty]) { expect(f.text).not.toHaveBeenCalled(); expect(f.zip).not.toHaveBeenCalled() }
  })
})
