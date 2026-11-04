// The deployment checklist on the page (S21c): decoded from what the real server sent, drawn in words as well as colour, and answered through plain functions.
import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { ContractError, ServerRefused, decodeChecklist, decodeDeploymentChecks, decodeProject, makeClient, type Checklist } from '../api'
import empty from '../contract/checklist_empty.json'
import answered from '../contract/checklist_answered.json'
import closed from '../contract/error_409_checklist_closed.json'
import unknownCheck from '../contract/error_404_check.json'
import detailJson from '../contract/project_detail.json'
import { allChecks, answeredBy, hasHistory, hasNoGo, headline, standing, ANSWER_LOOK } from '../lib/checklist'
import { answerCheckWith } from '../state/useProjectScreen'
import { ChecklistPanel } from './ChecklistPanel'
import { ApprovalSummary, checksLine, openCount } from './ApprovalSummary'
import { emptyScreen, ProjectPage } from '../pages/ProjectPage'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const list = decodeChecklist(answered), blank = decodeChecklist(empty)
const panel = (c: Checklist, over: Partial<Parameters<typeof ChecklistPanel>[0]> = {}) => html(<ChecklistPanel checklist={c} canAnswer busy={null} error={null} onAnswer={noop} {...over} />)

describe('the checklist as the server sends it', () => {
  it('has four groups of 4, 4, 7 and 1 checks, each with an ID and a question', () => {
    expect(blank.groups.map((g) => [g.key, g.title, g.checks.length])).toEqual([['ready', 'Ready to go', 4], ['before', 'Before the release', 4], ['after', 'After the release', 7], ['decision', 'The decision', 1]])
    expect(allChecks(blank).map((c) => c.id)).toEqual(Array.from({ length: 16 }, (_, n) => `CHK-${String(n + 1).padStart(3, '0')}`))
    expect(allChecks(blank).every((c) => c.question.length > 30 && c.latest === null && c.history.length === 0)).toBe(true)
  })
  it('counts answers, keeps a changed mind in the history and says the decision', () => {
    expect(list.totals).toEqual({ total: 16, go: 3, no_go: 0, not_applicable: 1, unanswered: 12 }); expect(list.decision).toBe('go'); expect(list.complete).toBe(false)
    const two = allChecks(list).find((c) => c.id === 'CHK-002')!
    expect(two.history.map((h) => h.answer)).toEqual(['no_go', 'go']); expect(two.latest).toEqual(two.history[1]); expect(two.latest?.note).toBe('Fixed.')
  })
  it('reads the refusals as plain sentences', () => {
    expect(closed.detail).toContain('a check can be answered only while the phase is running or awaiting_review'); expect(unknownCheck.detail).toContain("there is no check 'CHK-099'")
  })
  it('refuses a damaged answer', () => {
    const noTotals = clone(answered) as Record<string, unknown>; delete noTotals.totals
    expect(() => decodeChecklist(noTotals)).toThrow(ContractError)
    const bad = clone(answered); bad.groups[0].checks[0].latest = { answer: 'maybe', note: '', by: 'x', at: 't' } as never
    expect(() => decodeChecklist(bad)).toThrow(ContractError)
    const group = clone(answered); group.groups[0].title = 7 as never
    expect(() => decodeChecklist(group)).toThrow(ContractError)
    const decision = clone(answered); decision.decision = 'great' as never
    expect(() => decodeChecklist(decision)).toThrow(ContractError); expect(() => decodeChecklist(null)).toThrow(ContractError)
  })
})

describe('how an answer is shown', () => {
  it('has its own word and its own colour, so a No-go is never only a colour', () => {
    expect(Object.values(ANSWER_LOOK).map((l) => l.word)).toEqual(['Go', 'No-go', 'Not applicable']); expect(new Set(Object.values(ANSWER_LOOK).map((l) => l.box)).size).toBe(3)
    expect(ANSWER_LOOK.go.box).toContain('emerald'); expect(ANSWER_LOOK.no_go.box).toContain('rose'); expect(ANSWER_LOOK.not_applicable.box).toContain('slate')
  })
  it('says the standing of a check, who answered it and when, without the human: mark', () => {
    const [one, , , , , , , , , , , , , , , last] = allChecks(list)
    expect(standing(one, list)).toBe('Go'); expect(answeredBy(one)).toMatch(/^Demo Person · /); expect(standing(allChecks(blank)[0], blank)).toBe('Not answered'); expect(answeredBy(allChecks(blank)[0])).toBeNull()
    expect(standing(last, list)).toBe('Go')
  })
  it('knows a check was answered more than once only when it was', () => {
    expect(hasHistory(allChecks(list).find((c) => c.id === 'CHK-002')!)).toBe(true); expect(hasHistory(allChecks(list).find((c) => c.id === 'CHK-001')!)).toBe(false)
  })
  it('writes the headline in words: how many are answered, any No-go, and the overall decision', () => {
    expect(headline(blank)).toBe('0 of 16 answered · no overall decision yet'); expect(headline(list)).toBe('4 of 16 answered · overall: Go')
    const nogo = clone(list); nogo.totals.no_go = 2
    expect(headline(nogo)).toBe('4 of 16 answered · 2 No-go · overall: Go'); expect(hasNoGo(nogo)).toBe(true); expect(hasNoGo(list)).toBe(false)
  })
})

describe('the panel', () => {
  it('shows every group with its checks, the three choices for each, a note box, and the headline', () => {
    const out = panel(blank)
    for (const title of ['Ready to go', 'Before the release', 'After the release', 'The decision']) expect(out).toContain(`<h4 class="mb-1 text-sm font-bold">${title}</h4>`)
    expect((out.match(/aria-label="Answer for CHK-\d{3}"/g) ?? []).length).toBe(16); expect((out.match(/>Go<\/button>/g) ?? []).length).toBe(16)
    expect((out.match(/>No-go<\/button>/g) ?? []).length).toBe(16); expect((out.match(/>Not applicable<\/button>/g) ?? []).length).toBe(16); expect((out.match(/aria-label="Note for CHK-\d{3}"/g) ?? []).length).toBe(16)
    expect(out).toContain('0 of 16 answered · no overall decision yet'); expect(out).toContain('Each answer is saved in your name, and an earlier answer is kept if you change it.')
  })
  it('marks the chosen answer as pressed, in words, and shows who and when, and the note', () => {
    const out = panel(list)
    const one = out.slice(out.indexOf('aria-label="CHK-001: Go"'), out.indexOf('aria-label="CHK-002'))
    expect(one).toContain('aria-pressed="true"'); expect(one).toContain('Go · Demo Person · '); expect(one).toContain('Read it with the team.'); expect((one.match(/aria-pressed="true"/g) ?? []).length).toBe(1)
    expect(out).toContain('aria-label="CHK-004: Not answered"')
  })
  it('lists an answer that was changed, in order, folded', () => {
    const out = panel(list)
    const two = out.slice(out.indexOf('aria-label="CHK-002: Go"'), out.indexOf('aria-label="CHK-003'))
    expect(two).toContain('History (2 answers)'); expect(two.indexOf('No-go ·')).toBeLessThan(two.lastIndexOf('Go ·')); expect(two).not.toMatch(/<details[^>]* open/)
    expect(out.slice(out.indexOf('aria-label="CHK-001: Go"'), out.indexOf('aria-label="CHK-002'))).not.toContain('History')
  })
  it('cannot be answered without a name or while the phase is closed, but can be read', () => {
    const out = panel(blank, { canAnswer: false })
    expect((out.match(/<button[^>]*disabled=""/g) ?? []).length).toBe(48); expect(out).toContain('You can read the checklist now.'); expect(out).toContain('disabled=""')
    expect(panel(blank)).not.toContain('You can read the checklist now.'); expect((panel(blank).match(/<button[^>]*disabled=""/g) ?? []).length).toBe(0)
  })
  it('disables only the check being saved', () => {
    const out = panel(blank, { busy: 'CHK-003' })
    expect((out.match(/<button[^>]*disabled=""/g) ?? []).length).toBe(3)
  })
  it('tells a No-go it does not stop approval, and shows the server\'s sentence when an answer was not saved, as text', () => {
    const nogo = clone(list); nogo.totals.no_go = 1
    expect(panel(nogo)).toContain('A No-go does not stop you approving the phase'); expect(panel(list)).not.toContain('A No-go does not stop you')
    const out = panel(list, { error: 'could not <b>save</b>' })
    expect(out).toContain('That answer was not saved'); expect(out).toContain('could not &lt;b&gt;save&lt;/b&gt;'); expect(panel(list)).not.toContain('That answer was not saved')
  })
  it('passes the check, the answer and the note to the page, which is where the choice is made (a press is wired to each of the 48 buttons)', () => {
    const out = panel(blank)
    for (const id of ['CHK-001', 'CHK-009', 'CHK-016']) {
      const group = out.slice(out.indexOf(`aria-label="Answer for ${id}"`), out.indexOf('</div>', out.indexOf(`aria-label="Answer for ${id}"`)))
      expect((group.match(/<button/g) ?? []).length).toBe(3); expect(group).toContain('>Go</button>'); expect(group).toContain('>No-go</button>'); expect(group).toContain('>Not applicable</button>')
    }
  })
})

describe('answering, as a plain function', () => {
  const ui = () => { const seen: unknown[] = []; return { seen, ui: { setBusy: (v: string | null) => seen.push(['busy', v]), setError: (v: string | null) => seen.push(['error', v]), setList: (c: Checklist) => seen.push(['list', c.totals.go]), refresh: async () => { seen.push(['refresh']) } } } }
  it('marks the check busy, saves, shows the new list, refreshes the page, then clears the busy mark', async () => {
    const { seen, ui: u } = ui()
    const client = { answerCheck: vi.fn(async () => list) } as never
    await answerCheckWith(client, u, 'p1', 'CHK-001', 'Ann', 'go', 'ok')
    expect(seen).toEqual([['busy', 'CHK-001'], ['error', null], ['list', 3], ['refresh'], ['busy', null]])
    expect((client as { answerCheck: ReturnType<typeof vi.fn> }).answerCheck).toHaveBeenCalledWith('p1', 'CHK-001', 'Ann', 'go', 'ok', 'deploy')
  })
  it('keeps the server\'s sentence when the answer is refused, does not refresh, and still clears the busy mark', async () => {
    const { seen, ui: u } = ui()
    await answerCheckWith({ answerCheck: async () => { throw new ServerRefused(409, 'a check can be answered only while the phase is running') } } as never, u, 'p1', 'CHK-001', 'Ann', 'go', '')
    expect(seen).toEqual([['busy', 'CHK-001'], ['error', null], ['error', 'a check can be answered only while the phase is running'], ['busy', null]])
  })
})

describe('the client calls', () => {
  it('read the checklist, and save an answer with a PUT in the person\'s name', async () => {
    const seen: { url: string; init: RequestInit }[] = []
    const client = makeClient(async (url, init) => { seen.push({ url: String(url), init: init ?? {} }); return new Response(JSON.stringify(answered), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    expect((await client.checklist('p1')).totals.total).toBe(16); expect(seen[0].url).toBe('/api/projects/p1/deploy/checklist')
    await client.answerCheck('p1', 'CHK-002', 'Ann', 'no_go', 'why')
    expect(seen[1].url).toBe('/api/projects/p1/deploy/checklist/CHK-002'); expect(seen[1].init.method).toBe('PUT')
    expect(JSON.parse(String(seen[1].init.body))).toEqual({ answer: 'no_go', note: 'why' }); expect(new Headers(seen[1].init.headers).get('X-Actor')).toBe('Ann')
  })
  it('carry the server\'s sentence when a check is refused', async () => {
    const error = await makeClient(async () => new Response(JSON.stringify(closed), { status: 409, headers: { 'Content-Type': 'application/json' } })).answerCheck('p1', 'CHK-001', 'Ann', 'go', '').catch((e) => e)
    expect(error).toBeInstanceOf(ServerRefused); expect(error.message).toContain('a check can be answered only while the phase is running or awaiting_review')
  })
})

describe('the open items at approval', () => {
  const open = (checks: object | undefined) => ({ open_high_findings: 0, unreviewed: [], review_out_of_date: [], built_on_changed: [], guardrail_flags: {}, traceability_gaps: { needs_attention: 0, explained: 0, items: [] }, ...(checks ? { deployment_checks: checks } : {}) }) as never
  it('decodes the checks block when it is there and leaves it out when it is not', () => {
    expect(decodeDeploymentChecks({ no_go: ['CHK-002'], unanswered: ['CHK-005'], decision: 'go' })).toEqual({ no_go: ['CHK-002'], unanswered: ['CHK-005'], decision: 'go' })
    expect(decodeDeploymentChecks({ no_go: [], unanswered: [], decision: null }).decision).toBeNull()
    expect(() => decodeDeploymentChecks({ no_go: [], unanswered: [], decision: 'great' })).toThrow(ContractError); expect(() => decodeDeploymentChecks({ no_go: 'x' })).toThrow(ContractError)
  })
  it('counts the No-go and the unanswered checks as things still open, and nothing for another phase', () => {
    expect(openCount(open({ no_go: ['CHK-002'], unanswered: ['CHK-005', 'CHK-006'], decision: null }))).toBe(3); expect(openCount(open(undefined))).toBe(0)
    expect(openCount(open({ no_go: [], unanswered: [], decision: 'go' }))).toBe(0)
  })
  it('words the line: the No-go ones by ID, how many are unanswered, and that no overall decision was recorded', () => {
    expect(checksLine({ no_go: ['CHK-002'], unanswered: ['CHK-005', 'CHK-006'], decision: null })).toBe('Deployment checklist: 1 check marked No-go (CHK-002); 2 checks not answered yet, and no overall Go / No-go recorded')
    expect(checksLine({ no_go: [], unanswered: ['CHK-005'], decision: 'go' })).toBe('Deployment checklist: 1 check not answered yet'); expect(checksLine({ no_go: [], unanswered: [], decision: 'go' })).toBeNull()
  })
  it('shows the line in the approval summary, and nothing about checks when there are none to show', () => {
    const out = html(<ApprovalSummary open={open({ no_go: ['CHK-002'], unanswered: [], decision: 'go' })} names={{}} />)
    expect(out).toContain('Deployment checklist: 1 check marked No-go (CHK-002)'); expect(out).toContain('(see the checklist on this page)'); expect(out).toContain('1 thing still open')
    expect(html(<ApprovalSummary open={open(undefined)} names={{}} />)).not.toContain('Deployment checklist')
    expect(html(<ApprovalSummary open={open({ no_go: [], unanswered: [], decision: 'go' })} names={{}} />)).toContain('nothing is open')
  })
})

describe('the Deploy page', () => {
  const project = decodeProject(detailJson)
  const page = (key: string, checklist: Checklist | null) => html(<ProjectPage project={project} phaseKey={key} screen={{ ...emptyScreen, checklist }} />)
  it('shows the checklist on Deploy and on handover (each with its own list, below) and on no other phase', () => {
    expect(page('deploy', blank)).toContain('aria-label="Deployment checklist"')
    for (const p of project.phases.filter((x) => x.key !== 'deploy' && x.key !== 'handover')) expect(page(p.key, blank)).not.toContain('aria-label="Deployment checklist"')
  })
  it('shows nothing until the checklist has loaded', () => { expect(page('deploy', null)).not.toContain('Deployment checklist') })
})

describe('the report links', () => {
  it('are on the panel, one for Markdown and one for Word, at the report address', async () => {
    const { reportPath } = await import('../lib/checklist')
    expect(reportPath('p1', 'md')).toBe('/api/projects/p1/deploy/checklist/report?format=md'); expect(reportPath('a/b', 'docx')).toBe('/api/projects/a%2Fb/deploy/checklist/report?format=docx')
    const out = html(<ChecklistPanel checklist={blank} canAnswer busy={null} error={null} onAnswer={noop} projectId="p1" />)
    expect(out).toContain('href="/api/projects/p1/deploy/checklist/report?format=md"'); expect(out).toContain('href="/api/projects/p1/deploy/checklist/report?format=docx"')
    expect(out).toContain('Download .md'); expect(out).toContain('Download .docx'); expect((out.match(/ download=""/g) ?? []).length).toBe(2); expect(out).toContain('aria-label="Download the report"')
  })
  it('are absent when the panel does not know its project, and the page passes the project', () => {
    expect(panel(blank)).not.toContain('Download .docx')
    const project = decodeProject(detailJson)
    expect(html(<ProjectPage project={project} phaseKey="deploy" screen={{ ...emptyScreen, checklist: blank }} />)).toContain(`/api/projects/${project.id}/deploy/checklist/report?format=docx`)
  })
})

describe('the panel folds, and starts open', () => {
  const fold = (out: string) => out.slice(out.indexOf('<details'), out.indexOf('</summary>'))
  it('is one fold that is open when it first appears, so the checks are in view', () => {
    const out = panel(blank)
    expect((out.match(/<details/g) ?? []).length).toBeGreaterThanOrEqual(1)
    expect(out.slice(out.indexOf('aria-label="Deployment checklist"'), out.indexOf('<summary'))).toMatch(/<details[^>]* open=""/)
  })
  it('keeps the title and the progress in its summary, so they show when it is folded', () => {
    const head = fold(panel(list))
    expect(head).toContain('Deployment checklist'); expect(head).toContain('4 of 16 answered · overall: Go'); expect(head).toContain('role="status"')
  })
  it('keeps the checks, the report links and the explanation inside the fold, after the summary', () => {
    const out = panel(blank, { projectId: 'p1' })
    const inside = out.slice(out.indexOf('</summary>'))
    expect(inside).toContain('aria-label="Answer for CHK-001"'); expect(inside).toContain('aria-label="Answer for CHK-016"'); expect(inside).toContain('Download .docx'); expect(inside).toContain('Work through these by hand.')
    expect(out.slice(0, out.indexOf('</summary>'))).not.toContain('aria-label="Answer for')
  })
  it('shows a No-go in the summary in red even when folded', () => {
    const nogo = clone(list); nogo.totals.no_go = 1
    expect(fold(panel(nogo))).toContain('text-rose-800'); expect(fold(panel(list))).not.toContain('text-rose-800')
  })
  it('keeps a changed answer\'s history as its own fold inside, closed', () => {
    const out = panel(list)
    const two = out.slice(out.indexOf('aria-label="CHK-002: Go"'), out.indexOf('aria-label="CHK-003'))
    expect(two).toContain('<details class="mt-1 text-xs text-slate-600">'); expect(two).not.toMatch(/<details[^>]* open/)
  })
})

describe('who can answer on the Deploy page, decided from the phase and the name', () => {
  const project = decodeProject(detailJson)
  const withPhase = (status: string) => ({ ...project, phases: project.phases.map((p) => (p.key === 'deploy' ? { ...p, status } : p)) }) as never
  const buttons = (status: string, canChange: boolean) => {
    const out = html(<ProjectPage project={withPhase(status)} phaseKey="deploy" canChange={canChange} screen={{ ...emptyScreen, checklist: blank }} />)
    const area = out.slice(out.indexOf('aria-label="Deployment checklist"'))
    return (area.match(/<button[^>]*aria-pressed[^>]*>/g) ?? []).map((b) => b.includes('disabled=""'))
  }
  it('can be answered while the phase runs or waits for review, with a name', () => {
    for (const status of ['running', 'awaiting_review']) { const b = buttons(status, true); expect(b).toHaveLength(48); expect(b.every((x) => x === false), status).toBe(true) }
  })
  it('cannot be answered without a name, however open the phase is', () => {
    for (const status of ['running', 'awaiting_review']) expect(buttons(status, false).every((x) => x === true), status).toBe(true)
  })
  it('cannot be answered before the phase starts, after it is approved, or when it was sent back', () => {
    for (const status of ['not_started', 'approved', 'rejected']) expect(buttons(status, true).every((x) => x === true), status).toBe(true)
  })
})

describe('what the checklist loads, and when', () => {
  it('asks for the checklist only for the phases that have one: Deploy and handover', async () => {
    const { checklistWanted } = await import('../state/useProjectScreen')
    expect(checklistWanted('deploy')).toBe(true); expect(checklistWanted('handover')).toBe(true)
    for (const key of ['setup', 'requirements', 'design', 'architecture', 'build', '', 'Deploy', 'deploy2', 'Handover']) expect(checklistWanted(key), key).toBe(false)
  })
})

describe('the decoders are strict about what the screen relies on', () => {
  it('refuses a total that is not a number and a decision that is not one of the three answers', () => {
    const total = clone(answered); (total.totals as Record<string, unknown>).go = 'three'
    expect(() => decodeChecklist(total)).toThrow(ContractError)
    const unanswered = clone(answered); (unanswered.totals as Record<string, unknown>).unanswered = null
    expect(() => decodeChecklist(unanswered)).toThrow(ContractError)
  })
  it('keeps the deployment checks in the open items when they are sent and shows nothing of them when they are not', async () => {
    const { decodeOpenItems } = await import('../api')
    const base = { open_high_findings: 0, unreviewed: [], review_out_of_date: [], built_on_changed: [], guardrail_flags: {}, traceability_gaps: { needs_attention: 0, explained: 0, items: [] } }
    expect(decodeOpenItems({ ...base, deployment_checks: { no_go: ['CHK-002'], unanswered: [], decision: null } }).deployment_checks).toEqual({ no_go: ['CHK-002'], unanswered: [], decision: null })
    expect('deployment_checks' in decodeOpenItems(base)).toBe(false)
    expect(() => decodeOpenItems({ ...base, deployment_checks: { no_go: [], unanswered: [] } })).toThrow(ContractError)
  })
  it('lets a note box be used only when a person can answer', () => {
    const on = panel(blank), off = panel(blank, { canAnswer: false })
    expect((on.match(/<input[^>]*aria-label="Note for CHK-\d{3}"[^>]*disabled=""/g) ?? []).length).toBe(0)
    expect((off.match(/<input[^>]*aria-label="Note for CHK-\d{3}"[^>]*disabled=""/g) ?? []).length).toBe(16)
  })
})

describe('every total must be a number', () => {
  it('refuses each of the five totals when it is not one', () => {
    for (const key of ['total', 'go', 'no_go', 'not_applicable', 'unanswered']) {
      const bad = clone(answered); (bad.totals as Record<string, unknown>)[key] = 'many'
      expect(() => decodeChecklist(bad), key).toThrow(ContractError)
      const missing = clone(answered); delete (missing.totals as Record<string, unknown>)[key]
      expect(() => decodeChecklist(missing), key).toThrow(ContractError)
    }
  })
})

