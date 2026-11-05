// S23 Part C: the Templates tab. Decoded from the real server answers; static renders and plain functions. Nothing here uploads a file or reads a disk.
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ContractError, decodeProject, makeClient } from '../api'
import { decodeTemplates } from '../api/templates'
import empty from '../contract/templates_empty.json'
import saved from '../contract/templates_saved.json'
import e403 from '../contract/error_403_templates.json'
import e422 from '../contract/error_422_templates.json'
import detailJson from '../contract/project_detail.json'
import * as L from '../lib/templates'
import { ConfigurationView } from '../pages/ConfigurationPage'
import { TemplatesPanel, type TemplatesPanelProps } from './TemplatesPanel'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const E = decodeTemplates(empty), S = decodeTemplates(saved)
const panel = (over: Partial<TemplatesPanelProps> = {}) => html(<TemplatesPanel projectId="p1" view={S} busy={false} error={null} onUpload={noop} onRemove={noop} {...over} />)
const slot = (v: typeof S, category: string) => v.categories.find((c) => c.category === category)!

describe('the answers, as the server sends them', () => {
  it('decode six document types in order, none with a template for a new project', () => {
    expect(E.categories.map((c) => c.label)).toEqual(['Deployment plan', 'Release notes', 'Runbook', 'Hypercare plan', 'Deployment verification report', 'Handover sign-off report'])
    expect(E.categories.every((c) => c.template === null)).toBe(true); expect(E.can_change).toBe(true); expect(E.max_mb).toBe(5); expect(E.note).toContain('table of contents')
  })
  it('decode a stored template with its size, its date and whether it has a table of contents', () => {
    expect(slot(S, 'release_notes').template).toMatchObject({ category: 'release_notes', has_toc: true, size: 1000, uploaded_at: '2026-01-01T00:00:00Z' })
    expect(slot(S, 'runbook').template?.has_toc).toBe(false); expect(slot(S, 'runbook').template?.toc_note).toContain('No table of contents was found'); expect(slot(S, 'deployment_plan').template).toBeNull()
    expect(S.saved?.category).toBe('release_notes')
  })
  it('carry the refusals as plain sentences', () => {
    expect(e403.detail).toContain('only a Project Manager or an Administrator'); expect(e422.detail).toContain('not a Word document')
  })
  it('refuse a damaged answer', () => {
    const bad = clone(saved) as Record<string, unknown>; delete bad.can_change
    expect(() => decodeTemplates(bad)).toThrow(ContractError)
    const toc = clone(saved); (toc.categories[1].template as Record<string, unknown>).has_toc = 'yes'
    expect(() => decodeTemplates(toc)).toThrow(ContractError)
    const size = clone(saved); (size.categories[1].template as Record<string, unknown>).size = '1000'
    expect(() => decodeTemplates(size)).toThrow(ContractError)
    expect(() => decodeTemplates(null)).toThrow(ContractError)
  })
})

describe('the client calls', () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  it('list as the typed name, upload as multipart in the person\'s name, and remove with a DELETE', async () => {
    const seen: { url: string; init: RequestInit }[] = []
    const client = makeClient(async (url, init) => { seen.push({ url: String(url), init: init ?? {} }); return json(saved) })
    await client.templates('p1', 'Pam'); await client.templates('p1')
    const file = new Blob(['x'], { type: 'application/octet-stream' })
    await client.uploadTemplate('p 1', 'release_notes', file, 'rn.docx', 'Pam'); await client.removeTemplate('p1', 'runbook', 'Pam')
    expect(seen.map((s) => [s.init.method ?? 'GET', s.url])).toEqual([['GET', '/api/projects/p1/templates'], ['GET', '/api/projects/p1/templates'], ['POST', '/api/projects/p%201/templates/release_notes'], ['DELETE', '/api/projects/p1/templates/runbook']])
    expect(new Headers(seen[0].init.headers).get('X-Actor')).toBe('Pam'); expect(new Headers(seen[1].init.headers).get('X-Actor')).toBeNull()
    expect(new Headers(seen[2].init.headers).get('X-Actor')).toBe('Pam'); expect(new Headers(seen[2].init.headers).get('Content-Type')).toBeNull()                  // the browser sets the multipart boundary itself
    const form = seen[2].init.body as FormData
    expect(form).toBeInstanceOf(FormData); expect((form.get('file') as File).name).toBe('rn.docx')
  })
  it('carry the server\'s sentence when it says no', async () => {
    const e = await makeClient(async () => json(e403, 403)).uploadTemplate('p1', 'runbook', new Blob(['x']), 'a.docx', 'Ann').catch((x) => x)
    expect(e.message).toContain('only a Project Manager or an Administrator')
    const f = await makeClient(async () => json(e422, 422)).uploadTemplate('p1', 'runbook', new Blob(['x']), 'a.docx', 'Pam').catch((x) => x)
    expect(f.message).toContain('not a Word document')
  })
})

describe('a chosen file', () => {
  it('needs a name ending .docx, in any case', () => {
    for (const ok of ['a.docx', 'A.DOCX', ' My template.Docx ']) expect(L.looksLikeDocx(ok), ok).toBe(true)
    for (const bad of ['a.dotx', 'a.docm', 'a.doc', 'a.pdf', 'docx', 'a.docx.exe', '']) expect(L.looksLikeDocx(bad), bad).toBe(false)
  })
  it('is checked for a plain mistake before it is sent', () => {
    expect(L.fileProblem(null, 5)).toBeNull(); expect(L.fileProblem({ name: 'a.docx', size: 1000 }, 5)).toBeNull()
    expect(L.fileProblem({ name: 'a.pdf', size: 1000 }, 5)).toContain('.docx'); expect(L.fileProblem({ name: 'a.docx', size: 0 }, 5)).toBe('That file is empty.')
    expect(L.fileProblem({ name: 'a.docx', size: 5 * 1024 * 1024 + 1 }, 5)).toBe('That file is larger than the 5 MB limit for a template.'); expect(L.fileProblem({ name: 'a.docx', size: 5 * 1024 * 1024 }, 5)).toBeNull()
  })
})

describe('the words', () => {
  it('says a size in bytes, kilobytes or megabytes', () => {
    expect(L.sizeWords(500)).toBe('500 bytes'); expect(L.sizeWords(2048)).toBe('2 KB'); expect(L.sizeWords(3 * 1024 * 1024)).toBe('3.0 MB'); expect(L.sizeWords(1023)).toBe('1023 bytes'); expect(L.sizeWords(1024)).toBe('1 KB')
  })
  it('says a date plainly and never Invalid Date', () => {
    expect(L.whenWords('2026-11-05T10:00:00Z')).toBe('5 Nov 2026'); expect(L.whenWords('not a date')).toBe('not a date')
  })
  it('counts the types with a template and the ones that will be used', () => {
    expect(L.summary(E)).toEqual({ total: 6, have: 0, usable: 0 }); expect(L.summary(S)).toEqual({ total: 6, have: 2, usable: 1 })
    expect(L.summaryWords(E)).toBe('No templates yet. Documents use the standard layout.'); expect(L.summaryWords(S)).toBe('2 of 6 document types have a template; 1 will be used (the others have no table of contents).')
  })
  it('says who may change them', () => {
    expect(L.readOnlyNotice(S)).toBeNull(); expect(L.readOnlyNotice({ can_change: false })).toBe('Only a Project Manager or an Administrator can change templates. You can read and download them.')
    expect(L.canChange(S, false)).toBe(true); expect(L.canChange(S, true)).toBe(false); expect(L.canChange({ can_change: false }, false)).toBe(false)
  })
  it('builds the download address safely', () => {
    expect(L.downloadPath('p1', 'runbook')).toBe('/api/projects/p1/templates/runbook/download'); expect(L.downloadPath('a/b', 'x y')).toBe('/api/projects/a%2Fb/templates/x%20y/download')
  })
  it('says what was stored and whether it will be used', () => {
    expect(L.savedSentence(S.saved!)).toBe('Release notes template stored. It has a table of contents, so downloads of this document can use it.')
  })
})

describe('a change, step by step', () => {
  it('is busy while it runs and shows the new view', async () => {
    const log: unknown[] = []
    await L.runTemplateChange(async () => S, { setBusy: (b) => log.push(['busy', b]), setError: (m) => log.push(['error', m]), setView: (v) => log.push(['view', v.categories.length]) })
    expect(log).toEqual([['busy', true], ['error', null], ['view', 6], ['busy', false]])
  })
  it('keeps the server\'s sentence when refused and shows no new view', async () => {
    const log: unknown[] = []
    await L.runTemplateChange(async () => { throw new Error('this is not a Word document') }, { setBusy: (b) => log.push(['busy', b]), setError: (m) => log.push(['error', m]), setView: () => log.push('view') })
    expect(log).toEqual([['busy', true], ['error', null], ['error', 'this is not a Word document'], ['busy', false]])
  })
  it('sends the project, the document type, the file and the typed name', async () => {
    const seen: unknown[][] = []
    const client = { uploadTemplate: async (...a: unknown[]) => { seen.push(['upload', ...a]); return S }, removeTemplate: async (...a: unknown[]) => { seen.push(['remove', ...a]); return S } }
    const act = L.templateActions(client as never, 'p1', 'Pam')
    const file = new Blob(['x'])
    await act.upload('runbook', file, 'a.docx'); await act.remove('release_notes')
    expect(seen).toEqual([['upload', 'p1', 'runbook', file, 'a.docx', 'Pam'], ['remove', 'p1', 'release_notes', 'Pam']])
  })
})

describe('the tab', () => {
  it('shows a card for each of the six document types with the right look for each', () => {
    const out = panel()
    for (const c of S.categories) expect(out).toContain(`aria-label="${c.label}"`)
    expect(out).toContain('Will be used'); expect(out).toContain('Will not be used'); expect((out.match(/>No template</g) ?? []).length).toBe(4)
  })
  it('says what a template is, how many will be used, and nothing about a restart', () => {
    const out = panel()
    expect(out).toContain('A new upload replaces the old one'); expect(out).toContain('2 of 6 document types have a template; 1 will be used'); expect(out).not.toContain('Restart')
  })
  it('says for each stored template whether it has a table of contents, its size and its date', () => {
    const out = panel()
    expect(out).toContain('It has a table of contents, so downloads of this document can use it.'); expect(out).toContain('No table of contents was found in this file, so downloads will use the standard layout.')
    expect(out).toContain('1000 bytes'); expect(out).toContain('uploaded 1 Jan 2026')                                  // the fixture's size is 1000, under a kilobyte
  })
  it('offers a download of the original and a removal only for a type that has a template', () => {
    const out = panel()
    expect((out.match(/Download the original/g) ?? []).length).toBe(2); expect(out).toContain('href="/api/projects/p1/templates/release_notes/download"'); expect(out).toContain('aria-label="Remove the Release notes template"')
    expect(out).not.toContain('Remove the Deployment plan template'); expect(panel({ view: E })).not.toContain('Download the original')
  })
  it('offers a file picker for every type, taking only .docx, and says that uploading again replaces', () => {
    const out = panel({ view: E })
    expect((out.match(/type="file"/g) ?? []).length).toBe(6); expect((out.match(/accept="\.docx"/g) ?? []).length).toBe(6); expect(out).toContain('aria-label="Choose a Word file for Runbook"')
    expect(panel()).toContain('Uploading again replaces this one.')
  })
  it('turns every button off for someone who may only read, and says so', () => {
    const out = html(<TemplatesPanel projectId="p1" view={{ ...S, can_change: false }} busy={false} error={null} onUpload={noop} onRemove={noop} />)
    expect(out).toContain('Only a Project Manager or an Administrator can change templates'); expect(out).toMatch(/<input[^>]*type="file"[^>]*disabled=""/); expect(out).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Remove the Release notes template"|aria-label="Remove the Release notes template"[^>]*disabled=""/)
    expect(out).toContain('Download the original')                                                                  // reading and downloading stay open
  })
  it('turns every button off while a change is being sent', () => {
    const out = panel({ busy: true })
    expect(out).toMatch(/<input[^>]*type="file"[^>]*disabled=""/)
  })
  it('shows the saved message after an upload and a refusal as text', () => {
    expect(panel()).toContain('Release notes template stored.')
    const out = panel({ error: 'this is <b>not</b> a Word document' })
    expect(out).toContain('That could not be done'); expect(out).toContain('&lt;b&gt;not&lt;/b&gt;'); expect(out).not.toContain('<b>not</b>')
  })
  it('shows text from the server as text', () => {
    const v = clone(S); v.categories[0].label = '<img src=x>'; v.note = '<script>alert(1)</script>'
    const out = html(<TemplatesPanel projectId="p1" view={v} busy={false} error={null} onUpload={noop} onRemove={noop} />)
    expect(out).not.toContain('<img src=x>'); expect(out).not.toContain('<script>'); expect(out).toContain('&lt;script&gt;')
  })
})

describe('the Configuration page', () => {
  const project = decodeProject(detailJson)
  const view = (tab: 'users' | 'settings' | 'templates', templates: ReactElement | null) => html(<ConfigurationView project={project} tab={tab} onTab={noop} users={null} me={null} canEdit busy={false} error={null} templates={templates}
    actions={{ onAdd: noop, onRoles: noop, onActive: noop, onApprovers: noop }} />)
  it('shows the templates panel on its tab and not on the others', () => {
    const p = <p>TEMPLATES-HERE</p>
    expect(view('templates', p)).toContain('TEMPLATES-HERE'); expect(view('users', p)).not.toContain('TEMPLATES-HERE'); expect(view('settings', p)).not.toContain('TEMPLATES-HERE')
  })
  it('says it is loading until the templates arrive', () => { expect(view('templates', null)).toContain('Loading the templates') })
})


// ---- the survivors of the first sweep: the glue, as plain functions ------------------------------------------------------------------------------------

describe('choosing a file', () => {
  it('sends a good one, and sends nothing and says why for a bad one', () => {
    expect(L.pick({ name: 'a.docx', size: 1000 }, 5)).toEqual({ problem: null, send: true })
    expect(L.pick({ name: 'a.pdf', size: 1000 }, 5)).toEqual({ problem: 'A template must be a Word document with a name ending .docx.', send: false })
    expect(L.pick({ name: 'a.docx', size: 0 }, 5)).toEqual({ problem: 'That file is empty.', send: false })
    expect(L.pick(null, 5)).toEqual({ problem: null, send: false })                                                    // no file chosen: nothing to send and nothing to say
  })
})

describe('the controls of one document type', () => {
  it('upload to that type under the file\'s own name, and never to another', () => {
    const seen: unknown[][] = []
    const file = new File(['x'], 'My Template.docx')
    L.uploadFor((c, f, n) => seen.push([c, f, n]), 'hypercare_plan')(file); L.uploadFor((c, f, n) => seen.push([c, f, n]), 'runbook')(file)
    expect(seen).toEqual([['hypercare_plan', file, 'My Template.docx'], ['runbook', file, 'My Template.docx']])
  })
  it('remove that type and no other', () => {
    const seen: string[] = []
    L.removeFor((c) => seen.push(c), 'release_notes')(); L.removeFor((c) => seen.push(c), 'handover_signoff')()
    expect(seen).toEqual(['release_notes', 'handover_signoff'])
  })
})

describe('reading the templates as the person who is looking, for this project', () => {
  it('asks for this project with the typed name', async () => {
    const asked: unknown[][] = []
    const client = { templates: async (p: string, a?: string) => { asked.push([p, a]); return S } }
    await L.loadTemplates(client, 'p1', 'Pam'); await L.loadTemplates(client, 'p2', 'Ann Lee')
    expect(asked).toEqual([['p1', 'Pam'], ['p2', 'Ann Lee']])
  })
})

describe('the small details', () => {
  it('a kilobyte is 1024 bytes', () => { expect(L.sizeWords(1536)).toBe('2 KB'); expect(L.sizeWords(1500)).toBe('1 KB') })              // 1500 / 1024 = 1.46 -> 1; 1500 / 1000 would be 2
  it('a date is the date in UTC, whatever the computer\'s time zone', () => {
    expect(L.whenWords('2026-01-01T00:30:00Z')).toBe('1 Jan 2026'); expect(L.whenWords('2026-12-31T23:30:00Z')).toBe('31 Dec 2026')
  })
  it('a document type is encoded in an address like the project is', async () => {
    const urls: string[] = []
    const client = makeClient(async (url) => { urls.push(String(url)); return new Response(JSON.stringify(saved), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    await client.uploadTemplate('p1', 'a/b c', new Blob(['x']), 'a.docx', 'Pam'); await client.removeTemplate('p1', 'a/b c', 'Pam')
    expect(urls).toEqual(['/api/projects/p1/templates/a%2Fb%20c', '/api/projects/p1/templates/a%2Fb%20c'])
  })
  it('the file goes in the field the server reads, with its own name', async () => {
    let form: FormData | null = null
    const client = makeClient(async (_u, init) => { form = init?.body as FormData; return new Response(JSON.stringify(saved), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    await client.uploadTemplate('p1', 'runbook', new Blob(['abc']), 'Rb.docx', 'Pam')
    expect([...form!.keys()]).toEqual(['file']); expect((form!.get('file') as File).name).toBe('Rb.docx')
  })
})

describe('what the tab shows for each type', () => {
  it('says Will be used for a template with a table of contents and Will not be used for one without, on the right type', () => {
    const out = panel()
    const card = (label: string) => { const at = out.indexOf(`aria-label="${label}"`); return out.slice(at, out.indexOf('</li>', at)) }
    expect(card('Release notes')).toContain('Will be used'); expect(card('Release notes')).not.toContain('Will not be used')
    expect(card('Runbook')).toContain('Will not be used'); expect(card('Deployment plan')).not.toContain('Will be used')
  })
  it('offers each type\'s own download of the original', () => {
    const out = panel()
    const card = (label: string) => { const at = out.indexOf(`aria-label="${label}"`); return out.slice(at, out.indexOf('</li>', at)) }
    expect(card('Release notes')).toContain('href="/api/projects/p1/templates/release_notes/download"'); expect(card('Runbook')).toContain('href="/api/projects/p1/templates/runbook/download"')
    expect(card('Release notes')).not.toMatch(/<a [^>]*hidden/)
  })
  it('puts the picker for a bad file in the page with its alert, with no template and with one', () => {
    expect(panel({ view: E })).toContain('accept=".docx"'); expect(panel()).toContain('Uploading again replaces this one.')
  })
})


describe('the buttons of the tab, pressed', () => {
  type El = ReactElement<{ children?: unknown; onClick?: () => void; onPick?: (f: File) => void; label?: string; disabled?: boolean; 'aria-label'?: string }>
  const walk = (node: unknown, test: (e: El) => boolean, out: El[] = []): El[] => {
    if (Array.isArray(node)) { node.forEach((n) => walk(n, test, out)); return out }
    if (node && typeof node === 'object' && 'props' in node) { const el = node as El; if (test(el)) out.push(el); walk(el.props.children, test, out) }
    return out
  }
  const tree = (over: Partial<TemplatesPanelProps> = {}) => TemplatesPanel({ projectId: 'p1', view: S, busy: false, error: null, onUpload: noop, onRemove: noop, ...over })
  const pickers = (t: unknown) => walk(t, (e) => typeof e.type === 'function' && typeof e.props.onPick === 'function')

  it('has a picker for every type, and each uploads to its own type under the file\'s name', () => {
    const seen: unknown[][] = []
    const found = pickers(tree({ onUpload: (c, f, n) => seen.push([c, n]) }))
    expect(found).toHaveLength(6)
    const file = new File(['x'], 'Mine.docx')
    found.forEach((p) => p.props.onPick!(file))
    expect(seen.map((x) => x[0])).toEqual(S.categories.map((c) => c.category)); expect(seen.every((x) => x[1] === 'Mine.docx')).toBe(true)
  })
  it('has a Remove for each stored template, and each removes its own type', () => {
    const removed: string[] = []
    const buttons = walk(tree({ onRemove: (c) => removed.push(c) }), (e) => e.type === 'button' && /^Remove the .* template$/.test(e.props['aria-label'] ?? ''))
    expect(buttons.map((b) => b.props['aria-label'])).toEqual(['Remove the Release notes template', 'Remove the Runbook template'])
    buttons.forEach((b) => b.props.onClick!()); expect(removed).toEqual(['release_notes', 'runbook'])
  })
  it('turns the pickers and the Remove buttons off for a reader and while busy', () => {
    for (const over of [{ view: { ...S, can_change: false } }, { busy: true }]) {
      const t = tree(over)
      expect(pickers(t).every((p) => (p.props as { disabled?: boolean }).disabled === true)).toBe(true)
      expect(walk(t, (e) => e.type === 'button' && /^Remove the/.test(e.props['aria-label'] ?? '')).every((b) => b.props.disabled === true)).toBe(true)
    }
    expect(pickers(tree()).every((p) => (p.props as { disabled?: boolean }).disabled === false)).toBe(true)
  })
})
