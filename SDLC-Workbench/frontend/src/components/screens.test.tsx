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
    expect(out).toContain('Derived from')
    expect(out).toContain('Built on this')
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
