// S12b: the documents panel, search, artefact cards and reader, the run panel and the live project page, rendered to static HTML.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  decodeArtefactDetail, decodeArtefactList, decodeDocuments, decodeProject, decodeSearch, decodeUpload, type PhaseDetail, type ProjectDetail,
} from '../api'
import artefactDetailJson from '../contract/artefact_detail.json'
import artefactsJson from '../contract/artefacts.json'
import documentAddedJson from '../contract/document_added.json'
import documentsJson from '../contract/documents.json'
import detailJson from '../contract/project_detail.json'
import searchJson from '../contract/search.json'
import { actionSpecs } from '../lib/phaseActions'
import { emptyScreen, ProjectPage, type ProjectScreen } from '../pages/ProjectPage'
import { applyAll, idle, type Progress } from '../state/runProgress'
import { ArtefactCardView } from './ArtefactCard'
import { ArtefactReader } from './ArtefactReader'
import { DocumentsPanel } from './DocumentsPanel'
import { Flags } from './Flags'
import { RunPanel } from './RunPanel'
import { SafeMarkdown } from './SafeMarkdown'
import { SearchBox } from './SearchBox'

// React puts <!-- --> between neighbouring text nodes in static output; a person never sees it, so tests read the text without it.
const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const detail = decodeProject(detailJson)
const documents = decodeDocuments(documentsJson)
const upload = decodeUpload(documentAddedJson)
const cards = decodeArtefactList(artefactsJson)
const artefact = decodeArtefactDetail(artefactDetailJson)
const search = decodeSearch(searchJson)
const disabledButton = (label: string) => new RegExp(`<button[^>]*\\sdisabled=""[^>]*>${label}`)
const tags = (out: string) => [...out.matchAll(/<([a-z][a-z0-9]*)\b/gi)].map((m) => m[1].toLowerCase())

describe('documents panel', () => {
  const props = { documents, busy: false, error: null, lastUpload: null, onUpload: noop, onPaste: noop, onRemove: noop, canChange: true }
  it('has a way to choose a file and a place to paste text', () => {
    const out = html(<DocumentsPanel {...props} />)
    expect(out).toContain('Upload a document')
    expect(out).toContain('type="file"')
    expect(out).toContain('Paste text')
    expect(out).toContain('<textarea')
    expect(out).toContain('Add as document')
  })
  it('the paste button is off while busy, without a name, and while the box is empty', () => {
    expect(html(<DocumentsPanel {...props} />)).toMatch(disabledButton('<svg[^>]*>.*?</svg> Add as document'))      // empty box
    expect(html(<DocumentsPanel {...props} busy />)).toMatch(disabledButton('<svg[^>]*>.*?</svg> Add as document'))
    expect(html(<DocumentsPanel {...props} canChange={false} />)).toMatch(disabledButton('<svg[^>]*>.*?</svg> Add as document'))
  })
  it('the empty state says the agents will work from the brief alone', () => {
    expect(html(<DocumentsPanel {...props} documents={[]} />)).toContain('work from the brief alone')
  })
  it('each document shows its name, its citable ID, its size and who added it', () => {
    const out = html(<DocumentsPanel {...props} />)
    expect(out).toContain(documents[0].filename)
    expect(out).toContain(documents[0].source_id)
    expect(out).toContain(`Remove ${documents[0].filename}`)
    expect(out).toContain('added by Demo Person')
  })
  it('an upload with flags says where, never what', () => {
    const out = html(<DocumentsPanel {...props} lastUpload={upload} />)
    expect(out).toContain('flagged in')
    expect(out).toContain('an email address')
    expect(out).toContain(`line ${upload.flags[0].line}`)
    expect(out).not.toContain('jane.doe')
    expect(out).toContain('personal data: flagged, still saved')
  })
  it('the same file again says nothing changed', () => {
    expect(html(<DocumentsPanel {...props} lastUpload={{ ...upload, already_added: true, flags: [] }} />)).toContain('nothing changed')
  })
  it('a server refusal is shown as text', () => {
    const out = html(<DocumentsPanel {...props} error={'<script>x()</script> is not a supported file type'} />)
    expect(tags(out)).not.toContain('script')
    expect(out).toContain('&lt;script&gt;')
  })
  it('while busy, or without a name, the buttons are off', () => {
    expect(html(<DocumentsPanel {...props} busy />)).toMatch(disabledButton('<svg[^>]*>.*?</svg> Uploading…'))
    const noName = html(<DocumentsPanel {...props} canChange={false} />)
    expect((noName.match(/\sdisabled=""/g) ?? []).length).toBeGreaterThanOrEqual(3)
  })
  it('a filename with markup is text', () => {
    const out = html(<DocumentsPanel {...props} documents={[{ ...documents[0], filename: '<img src=x onerror=1>.md' }]} />)
    expect(tags(out)).not.toContain('img')
  })
})

describe('flags', () => {
  it('nothing flagged shows nothing', () => { expect(html(<Flags flags={[]} what="x" />)).toBe('') })
  it('a secret-class finding says it would have been refused', () => {
    expect(html(<Flags flags={[{ rule: 'aws_key_id', klass: 'secret', line: 3, heading: '', length: 20 }]} what="x" />)).toContain('would be refused in an artefact')
  })
  it('an unknown rule is shown by its own name rather than hidden', () => {
    expect(html(<Flags flags={[{ rule: 'new_rule', klass: 'personal', line: 1, heading: 'H', length: 1 }]} what="x" />)).toContain('new_rule')
  })
})

describe('search', () => {
  const props = { query: 'cancel', onQuery: noop, onSearch: noop, searching: false, result: search, error: null }
  it('each hit shows the ID it would be cited by, where it is from, and the passage', () => {
    const out = html(<SearchBox {...props} />)
    expect(out).toContain(search.hits[0].source_id)
    expect(out).toContain(search.hits[0].title)
    expect(out).toContain('24 hours')
  })
  it('no hits says so, naming the query', () => {
    expect(html(<SearchBox {...props} result={{ query: 'zebra', hits: [] }} />)).toContain('Nothing matches “zebra”')
  })
  it('the Search button is off while the box is empty', () => {
    expect(html(<SearchBox {...props} query="  " />)).toMatch(disabledButton('<svg[^>]*>.*?</svg> Search'))
    expect(html(<SearchBox {...props} />)).not.toMatch(disabledButton('<svg[^>]*>.*?</svg> Search'))
  })
  it('a hit with markup is text', () => {
    const evil = { ...search, hits: [{ ...search.hits[0], text: '<script>bad()</script>', title: '<b onmouseover=x>t</b>' }] }
    const out = html(<SearchBox {...props} result={evil} />)
    expect(tags(out)).not.toContain('script')
    expect(out).not.toContain('<b onmouseover')
  })
  it('an error is shown', () => { expect(html(<SearchBox {...props} result={null} error="type a word or a question to search for" />)).toContain('type a word') })
})

describe('artefact cards', () => {
  const card = cards.find((c) => c.type === 'functional_requirements')!
  it('an unwritten artefact says it is not written yet and cannot be opened', () => {
    const out = html(<ul><ArtefactCardView name="Personas" card={null} selected={false} onOpen={noop} /></ul>)
    expect(out).toContain('not written yet')
    expect(out).not.toContain('<button')
  })
  it('a written one shows its ID, version, author, attempts, items and cost', () => {
    const out = html(<ul><ArtefactCardView name="Functional requirements" card={card} selected={false} onOpen={noop} /></ul>)
    expect(out).toContain(card.id)
    expect(out).toContain(`version ${card.latest_version}`)
    expect(out).toContain('requirements analyst')
    expect(out).toContain('1 attempt')
    expect(out).toContain('2 items')
  })
  it('an unknown cost reads "unknown", never $0.00', () => {
    const out = html(<ul><ArtefactCardView name="X" card={{ ...card, cost_usd: null }} selected={false} onOpen={noop} /></ul>)
    expect(out).toContain('cost unknown')
    expect(out).not.toContain('$0.00')
  })
  it('flags show a count; none shows nothing', () => {
    expect(html(<ul><ArtefactCardView name="X" card={{ ...card, flags: 2 }} selected={false} onOpen={noop} /></ul>)).toContain('2 flags')
    expect(html(<ul><ArtefactCardView name="X" card={{ ...card, flags: 0 }} selected={false} onOpen={noop} /></ul>)).not.toContain('flag')
  })
  it('the selected card says so', () => {
    expect(html(<ul><ArtefactCardView name="X" card={card} selected onOpen={noop} /></ul>)).toContain('aria-pressed="true"')
  })
})

describe('the artefact reader', () => {
  const props = { artefact, onClose: noop, onVersion: noop }
  it('shows the body, how it was made, what it cites and what it connects to', () => {
    const out = html(<ArtefactReader {...props} />)
    expect(out).toContain(artefact.id)
    expect(out).toContain('demo-model')
    expect(artefact.sources.length).toBeGreaterThan(1)      // precondition: the fixture cites several sources
    expect(out).toContain(`What it cites (${artefact.sources.length})`)
    const cites = out.slice(out.lastIndexOf('<details', out.indexOf('aria-label="Sources"')), out.indexOf('aria-label="Connections"'))
    expect(cites.startsWith('<details')).toBe(true)
    expect(cites).not.toMatch(/^<details[^>]* open/)                      // folded until opened, every time the page is opened or refreshed
    expect(cites).toContain('<summary')
    expect(cites.match(/<details/g)!.length).toBe(1 + artefact.sources.length)       // the section, and one fold for each source inside it
    const links = out.slice(out.indexOf('aria-label="Connections"'), out.indexOf('</section>', out.indexOf('aria-label="Connections"')))
    expect(links.match(/<details/g)).toHaveLength(2)                                    // 'Derived from' and 'Built on this', each folded
    expect(links).not.toMatch(/<details[^>]* open/)                                      // closed every time the page is opened or refreshed
    expect(links).toContain(`Derived from (${artefact.links.derived_from.length})`)
    expect(links).toContain(`Built on this (${artefact.links.used_by.length})`)
    expect(out).toContain('FR-001')
  })
  it('a cited source shows its text; one that is gone says so and shows none', () => {
    const out = html(<ArtefactReader {...props} />)
    expect(out).toContain('Staff may book')
    expect(out).toContain('no longer available')
    expect(out).toContain('has been removed or replaced')
  })
  it('model-written Markdown cannot add a script, an image or a handler', () => {
    const evil = { ...artefact, body: '# Title\n\n<script>alert(1)</script>\n\n![x](http://a/b.png)\n\n[click](javascript:alert(1))\n\n<a href="#" onclick="x()">y</a>' }
    const out = html(<ArtefactReader {...props} artefact={evil} />)
    const body = out.slice(out.indexOf('<div class="markdown">'), out.indexOf('</div>', out.indexOf('<div class="markdown">')))
    expect(tags(body)).not.toContain('script')
    expect(tags(body)).not.toContain('img')
    expect(body).not.toMatch(/href="javascript/i)
    expect(body).not.toMatch(/<a[^>]*onclick/i)
    expect(body).toContain('<h1>Title</h1>')
  })
  it('a safe link opens in a new tab without the opener', () => {
    const out = html(<ArtefactReader {...props} artefact={{ ...artefact, body: '[docs](https://example.com/a)' }} />)
    expect(out).toContain('href="https://example.com/a"')
    expect(out).toContain('target="_blank"')
    expect(out).toContain('rel="noopener noreferrer nofollow"')
  })
  it('an older version says so and offers the latest', () => {
    expect(html(<ArtefactReader {...props} artefact={{ ...artefact, is_latest: false, version: 1, latest_version: 2 }} />)).toContain('This is an older version')
    expect(html(<ArtefactReader {...props} />)).not.toContain('older version')
  })
  it('why the first attempt was refused appears only when there was a repair, as text', () => {
    expect(html(<ArtefactReader {...props} />)).not.toContain('first attempt was refused')
    const g = { ...artefact.generation!, repair_reasons: [{ attempt: 1, problems: ['it cited <b>DOC-009#1</b>, which was not provided'] }] }
    const out = html(<ArtefactReader {...props} artefact={{ ...artefact, generation: g }} />)
    expect(out).toContain('Why the first attempt was refused')
    expect(out).toContain('&lt;b&gt;DOC-009#1')
  })
  it('the version list appears only when there are several, and marks the one shown', () => {
    expect(html(<ArtefactReader {...props} />)).not.toContain('aria-label="Versions"')
    const two = { ...artefact, versions: [artefact.versions[0], { number: 2, author: 'human:Ann', created_at: artefact.versions[0].created_at, human_edit: true }] }
    const out = html(<ArtefactReader {...props} artefact={two} />)
    expect(out).toContain('edited by Ann')
    expect(out.match(/aria-current="true"/g)).toHaveLength(1)
  })
  it('guardrail flags on the artefact are shown by place', () => {
    const g = { ...artefact.generation!, guardrails: [{ rule: 'email', klass: 'personal', line: 4, heading: 'H', length: 9 }] }
    expect(html(<ArtefactReader {...props} artefact={{ ...artefact, generation: g }} />)).toContain('line 4')
  })
  it('an unknown cost reads unknown', () => {
    expect(html(<ArtefactReader {...props} artefact={{ ...artefact, cost_usd: null }} />)).toContain('unknown')
  })
})

describe('safe markdown', () => {
  it('headings, lists, tables and code render', () => {
    const out = html(<SafeMarkdown>{'# H\n\n- a\n- b\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n`code`'}</SafeMarkdown>)
    for (const tag of ['h1', 'ul', 'li', 'table', 'code']) expect(tags(out)).toContain(tag)
  })
})

describe('the Build instruction set in the reader (S19)', () => {
  const detail = artefactDetailJson as never as Record<string, unknown>
  const body = ['## Overview', 'Two files.', '', '## Files', '- INS-001 00-foundation.md: Foundation.', '', '## Instructions',
    '=== FILE: 00-foundation.md ===', '# Foundation', '', '## Goal', 'A <b>booking</b> service.', '', '=== FILE: UC-001-reserve.md ===', '# Reserve', '', '## Goal', 'Reserve a room.', ''].join('\n')
  const show = (type: string, text: string) => html(<ArtefactReader artefact={decodeArtefactDetail({ ...detail, type, body: text })} onClose={noop} onVersion={noop} />)

  it('every file is folded: a closed <details> with its name and line count', () => {
    const out = show('build_instructions', body)
    const list = out.slice(out.indexOf('aria-label="Instruction files"'), out.indexOf('</ul>', out.indexOf('aria-label="Instruction files"')))
    expect(list.match(/<details/g)).toHaveLength(2)
    expect(out).not.toMatch(/<details[^>]* open/)
    expect(out).toContain('00-foundation.md')
    expect(out).toContain('UC-001-reserve.md')
    expect(out).toContain('4 lines')
  })
  it('each file has its own download button, named for the file', () => {
    const out = show('build_instructions', body)
    expect(out).toContain('aria-label="Download 00-foundation.md"')
    expect(out).toContain('Download UC-001-reserve.md')
    expect(out.match(/Download [A-Za-z0-9-]+\.md/g)).toHaveLength(4)       // the label and the visible text, for each of two files
  })
  it('the overview and the list of files stay visible above the folded files, and the marks are not shown as text', () => {
    const out = show('build_instructions', body)
    expect(out).toContain('Two files.')
    expect(out).toContain('INS-001 00-foundation.md')
    expect(out).not.toContain('=== FILE')
  })
  it('a file\'s text is rendered as Markdown with no raw HTML', () => {
    const out = show('build_instructions', body)
    expect(out).toContain('A &lt;b&gt;booking&lt;/b&gt; service.')
    expect(tags(out)).not.toContain('b')
  })
  it('an opened file folds its own code blocks, each closed and each downloadable', () => {
    const tests = ['# Acceptance tests', '', '## What the tests check', '### API-001 lists rooms', '```python', 'def test_a(): pass', '```', '', '### API-002 availability', '```python', 'def test_b(): pass', '```'].join('\n')
    const out = show('build_instructions', `## Overview\nx\n\n## Instructions\n=== FILE: 99-acceptance.md ===\n${tests}\n`)
    expect(out.match(/<details class="code-block/g)).toHaveLength(2)
    expect(out).not.toMatch(/<details[^>]* open/)
    expect(out).toContain('python block')
    expect(out).toContain('Download code.py')
    expect(out).toContain('def test_a(): pass')
  })
  it('with nothing cited the section is still there, folded, and says so when opened', () => {
    const out = show('low_level_design', '## Overview\nx\n')
    expect(out).toContain('What it cites (')
    const cites = out.slice(out.lastIndexOf('<details', out.indexOf('aria-label="Sources"')), out.indexOf('aria-label="Connections"'))
    expect(cites.startsWith('<details')).toBe(true)
    expect(cites).not.toMatch(/^<details[^>]* open/)
  })
  it('a file with findings shows how many, in the colour of the worst, and lists them inside the fold with their lines', () => {
    const review = { version_reviewed: 1, verdict: 'revise', summary: 's', findings: [
      { severity: 'low', target: '00-foundation.md:2', problem: 'minor thing', fix: 'tidy' }, { severity: 'high', target: '00-foundation.md:3', problem: 'wrong code', fix: 'use 409' },
      { severity: 'medium', target: 'UC-001-reserve.md', problem: 'unclear', fix: 'say it' }, { severity: 'high', target: 'General', problem: 'a gap', fix: '', source: 'system' }],
      independence: { label: 'independent', author_family: 'anthropic', reviewer_family: 'google', fell_back: false }, reviewer: { slot: 'gemini', model: 'm', family: 'google' },
      cost_usd: 0.1, attempts: 2, repair_reasons: [] }
    const out = html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'build_instructions', body, version: 1, review })} onClose={noop} onVersion={noop} />)
    const list = out.slice(out.indexOf('aria-label="Instruction files"'), out.indexOf('</ul>', out.indexOf('aria-label="Instruction files"') + 6000) + 5)
    expect(list).toContain('2 findings')
    expect(list).toContain('border-rose-300')
    expect(list).toContain('1 finding')
    expect(list).toContain('aria-label="Findings for 00-foundation.md"')
    expect(list).toContain('wrong code')
    expect(list).toContain('00-foundation.md:3')
    expect(list).not.toMatch(/<details[^>]* open/)
  })
  it('a file with no findings shows no count and no list', () => {
    const out = html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'build_instructions', body })} onClose={noop} onVersion={noop} />)
    expect(out).not.toContain('Findings for')
    expect(out).not.toMatch(/\d+ findings?</)
  })
  it('a review of an older version puts no finding on the files', () => {
    const review = { version_reviewed: 1, verdict: 'revise', summary: 's', findings: [{ severity: 'high', target: '00-foundation.md:3', problem: 'wrong code', fix: '' }],
      independence: { label: 'independent', author_family: 'anthropic', reviewer_family: 'google', fell_back: false }, reviewer: { slot: null, model: null, family: null }, cost_usd: null, attempts: 1, repair_reasons: [] }
    const out = html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'build_instructions', body, version: 2, latest_version: 2, review })} onClose={noop} onVersion={noop} />)
    expect(out).not.toContain('aria-label="Findings for 00-foundation.md"')
  })
  it('a finding from the system is labelled as such in the list, and a reviewer\'s is not', () => {
    const review = { version_reviewed: 1, verdict: 'revise', summary: 's', findings: [{ severity: 'high', target: '00-foundation.md:3', problem: 'from the system', fix: '', source: 'system' },
      { severity: 'low', target: '00-foundation.md:4', problem: 'from the reviewer', fix: '' }],
      independence: { label: 'independent', author_family: 'anthropic', reviewer_family: 'google', fell_back: false }, reviewer: { slot: null, model: null, family: null }, cost_usd: null, attempts: 1, repair_reasons: [] }
    const out = html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'build_instructions', body, version: 1, review })} onClose={noop} onVersion={noop} />)
    const labels = out.match(/found by the system/g) ?? []
    expect(labels.length).toBeGreaterThanOrEqual(2)                      // the same finding is listed under its file and in the review panel
    expect(out).toContain('from the reviewer')
  })
  it('a set\'s findings never colour-mark the text of another artefact the way item IDs do', () => {
    const review = { version_reviewed: 1, verdict: 'revise', summary: 's', findings: [{ severity: 'high', target: 'FR-001', problem: 'p', fix: '' }],
      independence: { label: 'independent', author_family: 'anthropic', reviewer_family: 'google', fell_back: false }, reviewer: { slot: null, model: null, family: null }, cost_usd: null, attempts: 1, repair_reasons: [] }
    const out = html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'low_level_design', review, version: 1 })} onClose={noop} onVersion={noop} />)
    expect(out).toContain('Review marks')                                 // an ordinary artefact still gets its colour marks and legend
  })
  const setReview = (findings: object[]) => ({ version_reviewed: 1, verdict: 'revise', summary: 's', findings,
    independence: { label: 'independent', author_family: 'anthropic', reviewer_family: 'google', fell_back: false }, reviewer: { slot: null, model: null, family: null }, cost_usd: null, attempts: 1, repair_reasons: [] })
  const readSet = (review: object) => html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'build_instructions', body, version: 1, review })} onClose={noop} onVersion={noop} />)
  const chipOf = (out: string, file: string) => {
    const at = out.indexOf(`>${file}</span>`)
    return out.slice(at, out.indexOf('</summary>', at))
  }
  it('the count beside a file is in the colour of its worst finding: red for high, amber for medium, blue for low', () => {
    const out = readSet(setReview([{ severity: 'high', target: '00-foundation.md:2', problem: 'p', fix: '' }, { severity: 'low', target: 'UC-001-reserve.md', problem: 'q', fix: '' }]))
    expect(chipOf(out, '00-foundation.md')).toContain('border-rose-300')
    expect(chipOf(out, '00-foundation.md')).not.toContain('border-sky-300')
    expect(chipOf(out, 'UC-001-reserve.md')).toContain('border-sky-300')
    const amber = readSet(setReview([{ severity: 'medium', target: '00-foundation.md', problem: 'p', fix: '' }]))
    expect(chipOf(amber, '00-foundation.md')).toContain('border-amber-300')
  })
  it('a set\'s findings are listed under its files and are not colour-marked on the text, so there is no marks legend', () => {
    const out = readSet(setReview([{ severity: 'high', target: '00-foundation.md:3', problem: 'p', fix: '' }, { severity: 'high', target: 'General', problem: 'g', fix: '' }]))
    expect(out).not.toContain('Review marks')
    expect(out).toContain('aria-label="Findings for 00-foundation.md"')
  })
  describe('Edit this file (S19f)', () => {
    const readFor = (props: object, over: object = {}) => html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'build_instructions', body, ...over })} onClose={noop} onVersion={noop} {...props} />)
    const setBody = body + '\n=== FILE: 02-design-index.md ===\n# Design index\n\nOne.\n'
    it('each editable file has an Edit this file button inside its fold, named for the file', () => {
      const out = readFor({ canEdit: true, onEditFile: noop })
      expect(out).toContain('aria-label="Edit 00-foundation.md"')
      expect(out).toContain('aria-label="Edit UC-001-reserve.md"')
      expect((out.match(/Edit this file/g) ?? []).length).toBe(2)
    })
    it('no button without the right to edit, without a handler, or on an older version', () => {
      expect(readFor({ onEditFile: noop })).not.toContain('Edit this file')
      expect(readFor({ canEdit: true })).not.toContain('Edit this file')
      expect(readFor({ canEdit: true, onEditFile: noop }, { is_latest: false, version: 1, latest_version: 2 })).not.toContain('Edit this file')
    })
    it('the design index, which the system writes, has no button', () => {
      const out = readFor({ canEdit: true, onEditFile: noop }, { body: setBody })
      expect(out).not.toContain('aria-label="Edit 02-design-index.md"')
      expect(out).toContain('aria-label="Edit 00-foundation.md"')
    })
    it('the whole-set edit stays, under a smaller name, and any other artefact keeps Edit by hand', () => {
      expect(readFor({ canEdit: true, onEdit: noop, onEditFile: noop })).toContain('Edit the whole set')
      const other = html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), type: 'low_level_design', body })} onClose={noop} onVersion={noop} canEdit onEdit={noop} onEditFile={noop} />)
      expect(other).toContain('Edit by hand'); expect(other).not.toContain('Edit this file'); expect(other).not.toContain('Edit the whole set')
    })
  })
  it('a set with no files says so', () => { expect(show('build_instructions', '## Overview\nNothing yet.\n')).toContain('holds no files') })
  it('any other artefact is shown as before, with no file list', () => {
    const out = show('low_level_design', body)
    expect(out).not.toContain('aria-label="Instruction files"')
    expect(out).not.toContain('Download 00-foundation.md')
  })
})

describe('the run panel', () => {
  const names = { personas: 'Personas', problem_statement: 'Problem statement', vision: 'Vision' }
  const run = (events: Parameters<typeof applyAll>[0]) => applyAll(events)
  const e = (id: number, type: string, data: Record<string, unknown>) => ({ id, type, run_id: 'r', at: 't', ...data }) as never
  const started = e(1, 'run.started', { phase: 'requirements', artefacts: ['personas', 'problem_statement', 'vision'], concurrency: 3, review: false, max_cost_usd: 2, max_seconds: 1800 })
  const props = { names, connected: true, cancelling: false, cancelNote: null, problem: null, onCancel: noop, onOpen: noop }
  it('nothing is shown before any run', () => { expect(html(<RunPanel {...props} progress={idle} />)).toBe('') })
  it('a live run shows a row per artefact, the cost against its cap, and a Cancel button', () => {
    const p = run([started, e(2, 'artefact.started', { key: 'personas' }), e(3, 'artefact.finished', { key: 'personas', artefact_id: 'REQ-PER-001', version: 1, attempts: 1, cost_usd: 0.0123, items: 2, flags: 0, author: 'agent:x@m' })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('Running')
    for (const n of ['Personas', 'Problem statement', 'Vision']) expect(out).toContain(n)
    expect(out).toContain('Done')
    expect(out).toContain('Waiting')
    expect(out).toContain('$0.0123')
    expect(out).toContain('of a $2.00 cap')
    expect(out).toContain('Cancel')
    expect(out).toContain('Read it')
    expect(out).toContain('<progress')
  })
  it('an artefact written in pieces lists its files with their state, open while it works', () => {
    const names2 = { ...names, build_instructions: 'Build instructions' }
    const p = run([e(1, 'run.started', { phase: 'build', artefacts: ['build_instructions'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 }), e(2, 'artefact.started', { key: 'build_instructions' }),
      e(3, 'piece.started', { key: 'build_instructions', file: '00-foundation.md', stage: 'foundation', index: 1, of: 4 }), e(4, 'piece.finished', { key: 'build_instructions', file: '00-foundation.md', attempts: 2, tokens_in: 1, tokens_out: 1, cost_usd: 0.0942 }),
      e(5, 'piece.started', { key: 'build_instructions', file: 'UC-001-a.md', stage: 'use_case', index: 2, of: 4 })])
    const out = html(<RunPanel {...props} names={names2} progress={p} />)
    expect(out).toContain('1 of 4 files written')
    expect(out).toContain('00-foundation.md')
    expect(out).toContain('UC-001-a.md')
    expect(out).toContain('written · 2 attempts · $0.0942')
    expect(out).toContain('writing')
    expect(out).toContain('2 attempts')
    expect(out).toContain('writing')
    expect(out).toContain('<details class="mt-1 text-xs text-slate-600" open="">')
  })
  it('a finished artefact folds its files away, and a failed file shows its reason as text', () => {
    const base2 = [e(1, 'run.started', { phase: 'build', artefacts: ['build_instructions'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 }), e(2, 'artefact.started', { key: 'build_instructions' }),
      e(3, 'piece.started', { key: 'build_instructions', file: 'a.md', stage: 'foundation', index: 1, of: 1 })]
    const done = html(<RunPanel {...props} names={{ build_instructions: 'Build instructions' }} progress={run([...base2, e(4, 'piece.finished', { key: 'build_instructions', file: 'a.md', attempts: 1, tokens_in: 1, tokens_out: 1, cost_usd: 0.01 }),
      e(5, 'artefact.finished', { key: 'build_instructions', artefact_id: 'BLD-INS-001', version: 1, attempts: 1, cost_usd: 0.01, items: 1, flags: 0, author: 'agent:x@m' })])} />)
    expect(done).toContain('1 of 1 files written')
    expect(done).not.toContain(' open=""')
    const bad = html(<RunPanel {...props} names={{ build_instructions: 'Build instructions' }} progress={run([...base2, e(4, 'piece.failed', { key: 'build_instructions', file: 'a.md', reason: 'bad <b>file</b>' }),
      e(5, 'artefact.failed', { key: 'build_instructions', reason: 'x' })])} />)
    expect(bad).toContain('bad &lt;b&gt;file&lt;/b&gt;')
    expect(tags(bad)).not.toContain('b')
    expect(bad).toContain('open=""')
    expect(bad).toContain('failed')
  })
  it('each file state has its own word, not the word of another state', () => {
    const lead = [e(1, 'run.started', { phase: 'build', artefacts: ['build_instructions'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 }), e(2, 'artefact.started', { key: 'build_instructions' })]
    const piece = (id: number, type: string, file: string, extra: Record<string, unknown> = {}) => e(id, type, { key: 'build_instructions', file, ...extra })
    const out = html(<RunPanel {...props} names={{ build_instructions: 'Build instructions' }} progress={run([...lead,
      piece(3, 'piece.started', 'w.md', { stage: 'foundation', index: 1, of: 3 }), piece(4, 'piece.started', 'd.md', { stage: 'use_case', index: 2, of: 3 }), piece(5, 'piece.started', 'f.md', { stage: 'use_case', index: 3, of: 3 }),
      piece(6, 'piece.finished', 'd.md', { attempts: 1, tokens_in: 1, tokens_out: 1, cost_usd: 0.01 }), piece(7, 'piece.failed', 'f.md', { reason: 'no' })])} />)
    const state = (file: string) => (out.match(new RegExp(`${file.replace('.', '\\.')}</span><span class="text-slate-500">([a-z]+)`)) ?? [])[1]
    expect([state('w.md'), state('d.md'), state('f.md')]).toEqual(['writing', 'written', 'failed'])
  })
  it('the guide and the screen files are listed like any other file, in the order they started', () => {
    const lead = [e(1, 'run.started', { phase: 'build', artefacts: ['build_instructions'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 }), e(2, 'artefact.started', { key: 'build_instructions' })]
    const go = (id: number, file: string, stage: string, index: number) => e(id, 'piece.started', { key: 'build_instructions', file, stage, index, of: 4 })
    const out = html(<RunPanel {...props} names={{ build_instructions: 'Build instructions' }} progress={run([...lead, go(3, '00-foundation.md', 'foundation', 1), go(4, '01-ui-guidelines.md', 'ui_guide', 2), go(5, 'UI-HFS-001-browse.md', 'screen', 3)])} />)
    expect(out.indexOf('00-foundation.md')).toBeLessThan(out.indexOf('01-ui-guidelines.md'))
    expect(out.indexOf('01-ui-guidelines.md')).toBeLessThan(out.indexOf('UI-HFS-001-browse.md'))
    expect(out).toContain('0 of 4 files written')
  })
  it('a row with no files shows no file list', () => {
    expect(html(<RunPanel {...props} progress={run([started, e(2, 'artefact.started', { key: 'personas' })])} />)).not.toContain('files written')
  })
  it('a finished run has no Cancel button', () => {
    const p = run([started, e(2, 'run.finished', { status: 'finished', reason: null, totals: { artefacts: { done: 3, failed: 0, skipped: 0, not_started: 0 }, calls: 3, cost_usd: 0.05, cost_is_partial: false, tokens_in: 1, tokens_out: 1, elapsed_seconds: 4, over_budget_by_usd: null } })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('Finished')
    expect(out).not.toContain('Cancel')
    expect(out).toContain('$0.0500')
    expect(out).toContain('3 model calls')
  })
  it('a stopped run says why, in a sentence', () => {
    const totals = { artefacts: { done: 0, failed: 0, skipped: 0, not_started: 3 }, calls: 0, cost_usd: 0, cost_is_partial: false, tokens_in: 0, tokens_out: 0, elapsed_seconds: 1, over_budget_by_usd: null }
    const out = html(<RunPanel {...props} progress={run([started, e(2, 'run.stopped', { status: 'stopped', reason: 'cancelled', totals })])} />)
    expect(out).toContain('The run stopped early')
    expect(out).toContain('you cancelled it')
    expect(out).toContain('not started: the run was stopped (cancelled)')
  })
  it('a failed artefact and its skipped dependants show the server\'s reasons as text', () => {
    const p = run([started, e(2, 'artefact.failed', { key: 'personas', reason: 'blocked <i>by</i> the model' }), e(3, 'artefact.skipped', { key: 'vision', reason: 'blocked by personas' })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('Failed')
    expect(out).toContain('Skipped')
    expect(out).toContain('blocked by personas')
    expect(tags(out)).not.toContain('i')
  })
  it('a failed row can show WHY, from the run\'s stored record: what the checks said, as text', () => {
    const p = run([started, e(2, 'artefact.failed', { key: 'personas', reason: 'the reply failed its checks after 3 attempt(s) (1 problem(s))' })])
    const out = html(<RunPanel {...props} progress={p} failures={{ personas: { reason: 'x', problems: ['the section <b>Purpose</b> is missing'], cut_off: false } }} />)
    expect(out).toContain('What the checks said')
    expect(out).toContain('the section &lt;b&gt;Purpose&lt;/b&gt; is missing')
    expect(tags(out)).not.toContain('b')
    expect(out).not.toContain('output limit')
  })
  it('a reply cut off at its limit says so and names the setting', () => {
    const p = run([started, e(2, 'artefact.failed', { key: 'personas', reason: 'cut off' })])
    const out = html(<RunPanel {...props} progress={p} failures={{ personas: { reason: 'x', problems: [], cut_off: true } }} />)
    expect(out).toContain('Why: the reply was cut off at its output limit')
    expect(out).toContain('AGENT_OUTPUT_TOKENS_BY_ROLE')
    expect(out).not.toContain('What the checks said')
  })
  it('a failed row with no stored detail shows only its short reason, as before', () => {
    const p = run([started, e(2, 'artefact.failed', { key: 'personas', reason: 'a short reason' })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('a short reason')
    expect(out).not.toContain('<details')
  })
  it('details are shown only for a row that FAILED, never for a done or waiting one', () => {
    const p = run([started, e(2, 'artefact.started', { key: 'personas' })])
    const out = html(<RunPanel {...props} progress={p} failures={{ personas: { reason: 'x', problems: ['old'], cut_off: false }, vision: { reason: 'y', problems: ['old'], cut_off: false } }} />)
    expect(out).not.toContain('<details')
  })
  it('a collapsed section: the details are closed until opened', () => {
    const p = run([started, e(2, 'artefact.failed', { key: 'personas', reason: 'r' })])
    const out = html(<RunPanel {...props} progress={p} failures={{ personas: { reason: 'x', problems: ['one'], cut_off: false } }} />)
    expect(out).toContain('<details class="mt-1')
    expect(out).not.toMatch(/<details[^>]*\sopen/)
  })
  it('an unknown cost is "unknown", not $0.00', () => {
    const p = run([started, e(2, 'artefact.finished', { key: 'personas', artefact_id: 'A', version: 1, attempts: 1, cost_usd: null, items: 0, flags: 0, author: 'a' })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('unknown (a call had no price)')
    expect(out).not.toContain('$0.00')
  })
  it('reconnecting is shown while live and not connected, and the cancel note and problems are shown', () => {
    const p = run([started])
    expect(html(<RunPanel {...props} progress={p} connected={false} />)).toContain('reconnecting')
    expect(html(<RunPanel {...props} progress={p} cancelNote="No new artefact will start." />)).toContain('No new artefact will start.')
    expect(html(<RunPanel {...props} progress={p} problem="an event could not be read" />)).toContain('an event could not be read')
    expect(html(<RunPanel {...props} progress={p} cancelling />)).toMatch(disabledButton('<svg[^>]*>.*?</svg> Cancelling…'))
  })
  it('a failed artefact shows the attempts that happened: a failure after three says attempt 3, not 4', () => {
    const tries = [1, 2, 3].map((n, i) => e(3 + i, 'artefact.attempt', { key: 'personas', attempt: n, will_repair: true, problems: 1, fell_back: false }))
    const p = run([started, e(2, 'artefact.started', { key: 'personas' }), ...tries, e(6, 'artefact.failed', { key: 'personas', reason: 'the reply failed its checks after 3 attempt(s) (1 problem(s))' })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('Failed'); expect(out).toContain('attempt 3'); expect(out).not.toContain('attempt 4')
  })
  it('a retrying artefact shows its attempt number', () => {
    const p = run([started, e(2, 'artefact.started', { key: 'personas' }), e(3, 'artefact.attempt', { key: 'personas', attempt: 1, will_repair: true, problems: 1, fell_back: false })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('Retrying')
    expect(out).toContain('attempt 2')
  })
  it('a run that failed without totals says why, as text, and what is kept', () => {
    const p = run([started, e(2, 'run.stopped', { status: 'failed', reason: '<b>it broke</b>', totals: null })])
    const out = html(<RunPanel {...props} progress={p} />)
    expect(out).toContain('The run failed')
    expect(out).toContain('&lt;b&gt;it broke')
    expect(out).toContain('What had finished is kept')
    expect(tags(out)).not.toContain('b')
  })
  it('an interrupted run says what is kept', () => {
    const totals = { artefacts: { done: 1, failed: 0, skipped: 0, not_started: 2 }, calls: 1, cost_usd: 0.01, cost_is_partial: false, tokens_in: 1, tokens_out: 1, elapsed_seconds: 1, over_budget_by_usd: null }
    expect(html(<RunPanel {...props} progress={run([started, e(2, 'run.stopped', { status: 'interrupted', reason: 'the backend stopped while this run was in progress', totals: null })])} />)).toContain('What had finished is kept')
  })
})

describe('the live project page', () => {
  const phaseOf = (key: string): PhaseDetail => detail.phases.find((p) => p.key === key)!
  const withPhase = (key: string, patch: Partial<PhaseDetail>): ProjectDetail => ({ ...detail, phases: detail.phases.map((p) => (p.key === key ? { ...p, ...patch } : p)) })

  it('Run is a working button on a phase that can run, with the mode\'s own hint', () => {
    const out = html(<ProjectPage project={detail} phaseKey="setup" />)
    expect(out).toContain('Run this phase')
    expect(out).not.toMatch(disabledButton('Run this phase'))
    expect(out).toContain('free and offline')
    expect(html(<ProjectPage project={{ ...detail, mode: 'live' }} phaseKey="setup" />)).toContain('this costs money')
  })
  it('exactly the buttons the server allows appear, with their words', () => {
    for (const [status, actions, shown, hidden] of [
      ['running', ['run', 'finish'], ['Run it again', 'Hand to review'], ['Approve']],
      ['awaiting_review', ['approve', 'request_changes'], ['Approve', 'Request changes'], ['Hand to review', 'Run it again']],
      ['approved', [], [], ['Approve', 'Hand to review', 'Run it again']],
    ] as const) {
      const out = html(<ProjectPage project={withPhase('setup', { status, allowed_actions: [...actions] })} phaseKey="setup" />)
      const buttons = [...out.matchAll(/<button[^>]*>([^<]*)<\/button>/g)].map((m) => m[1])      // button words only: the status pill also says "Approved"
      for (const s of shown) expect(buttons, `${status} shows ${s}`).toContain(s)
      for (const h of hidden) expect(buttons, `${status} hides ${h}`).not.toContain(h)
    }
  })
  it('Request changes is a working button now, with a sentence saying what it does', () => {
    const out = html(<ProjectPage project={withPhase('setup', { status: 'awaiting_review', allowed_actions: ['approve', 'request_changes'] })} phaseKey="setup" />)
    expect(out).not.toMatch(disabledButton('Request changes'))
    expect(out).toContain('Choose the artefacts to rewrite and say what is wrong with each.')
    expect(out).not.toContain('Coming in the next slice')
  })
  it('approving with nothing open says "Approve"; with anything open it says "Approve anyway" and that nothing stops you', () => {
    const specs = (open: number) => actionSpecs({ ...detail.phases[0], status: 'awaiting_review', allowed_actions: ['approve'] }, 'live', open)
    expect(specs(0)[0].label).toBe('Approve')
    expect(specs(0)[0].hint).toBe('Records your approval in the audit trail.')
    expect(specs(3)[0].label).toBe('Approve anyway')
    expect(specs(3)[0].hint).toBe('Records your approval, and what was still open, in the audit trail. Nothing stops you.')
  })
  it('while a run is going, only Run is considered and the others are off', () => {
    const screen: ProjectScreen = { ...emptyScreen, runLive: true }
    const out = html(<ProjectPage project={withPhase('setup', { status: 'running', allowed_actions: ['run', 'finish'] })} phaseKey="setup" screen={screen} />)
    expect(out).toMatch(disabledButton('Hand to review'))
  })
  it('buttons are off while another action is in flight, and without a name', () => {
    const busy = html(<ProjectPage project={detail} phaseKey="setup" screen={{ ...emptyScreen, busy: 'run' }} />)
    expect(busy).toMatch(disabledButton('Run this phase…'))
    expect(html(<ProjectPage project={detail} phaseKey="setup" canChange={false} />)).toMatch(disabledButton('Run this phase'))
  })
  it('an error from an action is shown as text', () => {
    expect(html(<ProjectPage project={detail} phaseKey="setup" screen={{ ...emptyScreen, actionError: '<i>Requirements</i> cannot start yet' }} />)).toContain('&lt;i&gt;Requirements')
  })
  it('written artefacts appear as cards in their phase and nowhere else', () => {
    const inRequirements = html(<ProjectPage project={detail} phaseKey="requirements" screen={{ ...emptyScreen, cards }} />)
    expect(inRequirements).toContain(cards[0].id)
    const inSetup = html(<ProjectPage project={detail} phaseKey="setup" screen={{ ...emptyScreen, cards }} />)
    expect(inSetup).not.toContain(cards[0].id)
  })
  it('the reader opens under the phase when an artefact is chosen', () => {
    const out = html(<ProjectPage project={detail} phaseKey="requirements" screen={{ ...emptyScreen, cards, open: artefact }} />)
    expect(out).toContain('What it cites')
    expect(out).toContain('aria-pressed="true"')
  })
  it('the run panel appears only for the phase being run', () => {
    const progress: Progress = applyAll([{ id: 1, type: 'run.started', run_id: 'r', at: 't', phase: 'requirements', artefacts: ['personas'], concurrency: 3, review: false, max_cost_usd: 2, max_seconds: 1800 }])
    expect(html(<ProjectPage project={detail} phaseKey="requirements" screen={{ ...emptyScreen, progress }} />)).toContain('aria-label="Run progress"')
    expect(html(<ProjectPage project={detail} phaseKey="setup" screen={{ ...emptyScreen, progress }} />)).not.toContain('aria-label="Run progress"')
  })
  it('the documents and the search box are on the page', () => {
    const out = html(<ProjectPage project={detail} phaseKey="setup" screen={{ ...emptyScreen, documents }} />)
    expect(out).toContain('Reference documents')
    expect(out).toContain('Search the project')
    expect(out).toContain(documents[0].filename)
  })
  it('an approved phase says who approved it', () => {
    expect(html(<ProjectPage project={withPhase('setup', { status: 'approved', decided_by: 'human:Ann', decision: 'approve', allowed_actions: [] })} phaseKey="setup" />)).toContain('Approved by Ann.')
  })
})

describe('what each button says', () => {
  const phase = (status: PhaseDetail['status'], allowed: PhaseDetail['allowed_actions']): PhaseDetail => ({ ...detail.phases[0], status, allowed_actions: allowed })
  it('a phase that already ran says "Run it again"; a fresh one says "Run this phase"', () => {
    expect(actionSpecs(phase('not_started', ['run']), 'replay')[0].label).toBe('Run this phase')
    expect(actionSpecs(phase('running', ['run']), 'replay')[0].label).toBe('Run it again')
    expect(actionSpecs(phase('rejected', ['run']), 'replay')[0].label).toBe('Run it again')
  })
  it('every action is wired now', () => {
    const specs = actionSpecs(phase('awaiting_review', ['approve', 'request_changes', 'run', 'finish']), 'replay')
    expect(specs.filter((s) => !s.live)).toEqual([])
  })
  it('a sent-back phase offers to rewrite exactly the artefacts that have a note, by count', () => {
    const sentBack = (n: number) => actionSpecs(phase('rejected', ['run']), 'live', 0, n)[0]
    expect(sentBack(2).label).toBe('Rewrite the 2 sent back')
    expect(sentBack(2).hint).toContain('only the artefacts you sent back')
    expect(sentBack(0).label).toBe('Run it again')                       // nothing sent back: an ordinary re-run
  })
  it('it words exactly the actions the server allowed, in the server\'s order', () => {
    expect(actionSpecs(phase('running', ['finish', 'run']), 'live').map((s) => s.action)).toEqual(['finish', 'run'])
    expect(actionSpecs(phase('approved', []), 'live')).toEqual([])
  })
})


type Link = { from: string; kind: string; to: string }

describe('the connections of an artefact are folded (2026-11-05)', () => {
  const show = (links: { derived_from: Link[]; used_by: Link[] }) =>
    html(<ArtefactReader artefact={decodeArtefactDetail({ ...(artefactDetailJson as object), links }) } onClose={noop} onVersion={noop} />)
  const section = (out: string) => out.slice(out.indexOf('aria-label="Connections"'), out.indexOf('</section>', out.indexOf('aria-label="Connections"')))
  const many = Array.from({ length: 40 }, (_, n) => ({ from: 'INS-001', kind: 'derives', to: `UC-${String(n + 1).padStart(3, '0')}` }))

  it('forty links are one closed heading with the count, and every link is still in the page for a reader to open', () => {
    const out = section(show({ derived_from: many, used_by: [] }))
    expect(out).toContain('Derived from (40)')
    expect(out).not.toMatch(/<details[^>]* open/)
    expect(out).toContain('UC-040')
  })
  it('an empty list is still a folded heading with a zero, and says so when opened', () => {
    const out = section(show({ derived_from: [], used_by: [] }))
    expect(out).toContain('Derived from (0)')
    expect(out).toContain('Built on this (0)')
    expect(out).toContain('Nothing upstream is linked.')
    expect(out).toContain('Nothing is built on it yet.')
    expect(out).not.toMatch(/<details[^>]* open/)
  })
  it('each list is its own fold, so opening one does not open the other', () => {
    const out = section(show({ derived_from: many.slice(0, 2), used_by: [{ from: 'UC-001', kind: 'derives', to: 'INS-001' }] }))
    expect(out.match(/<details/g)).toHaveLength(2)
    expect(out).toContain('Derived from (2)')
    expect(out).toContain('Built on this (1)')
  })
  it('a link is shown from, then an arrow, then to', () => {
    const out = section(show({ derived_from: [{ from: 'INS-001', kind: 'derives', to: 'UC-001' }], used_by: [] }))
    expect(out.indexOf('INS-001')).toBeLessThan(out.indexOf('UC-001'))
  })
})
