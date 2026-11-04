// S22c: BAU handover's sign-off on the page. The same checklist panel and record as Deploy's, decoded from what the real server sent, in the sign-off's own words
// (Accept / Not accepted), shown on the Handover page beside the blue "done by hand" card, and counted in the approval summary in its own words.
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeChecklist, decodeOpenItems, decodeProject, type Checklist } from '../api'
import empty from '../contract/signoff_empty.json'
import answered from '../contract/signoff_answered.json'
import deployList from '../contract/checklist_answered.json'
import detailJson from '../contract/project_detail.json'
import { allChecks, answeredBy, hasHistory, headline, standing, wordFor } from '../lib/checklist'
import { ChecklistPanel } from './ChecklistPanel'
import { ApprovalSummary, SIGNOFF_WORDING, checksLine, openCount } from './ApprovalSummary'
import { emptyScreen, ProjectPage } from '../pages/ProjectPage'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const blank = decodeChecklist(empty), list = decodeChecklist(answered)
const panel = (c: Checklist) => html(<ChecklistPanel checklist={c} canAnswer busy={null} error={null} onAnswer={noop} projectId="p1" />)

describe('the sign-off as the server sends it', () => {
  it('says what it is: handover, titled, with accept and not accepted for the answers', () => {
    expect(blank.phase).toBe('handover'); expect(blank.title).toBe('Handover sign-off'); expect(blank.answer_words).toEqual({ go: 'Accept', no_go: 'Not accepted', not_applicable: 'Not applicable' })
    expect(blank.decision_check).toBe('SGN-008')
  })
  it('has eight statements in three groups, 3, 4 and 1, each with an ID and a statement', () => {
    expect(blank.groups.map((g) => [g.key, g.title, g.checks.length])).toEqual([['given', 'What support has been given', 3], ['can', 'What support can do', 4], ['decision', 'The decision', 1]])
    expect(allChecks(blank).map((c) => c.id)).toEqual(Array.from({ length: 8 }, (_, n) => `SGN-${String(n + 1).padStart(3, '0')}`))
    expect(allChecks(blank).every((c) => c.question.length > 30 && c.latest === null && c.history.length === 0)).toBe(true)
  })
  it('counts answers, keeps a changed mind in the history and says the decision', () => {
    expect(list.totals).toEqual({ total: 8, go: 3, no_go: 0, not_applicable: 1, unanswered: 4 }); expect(list.decision).toBe('go'); expect(list.complete).toBe(false)
    const two = allChecks(list).find((c) => c.id === 'SGN-002')!
    expect(two.history.map((h) => h.answer)).toEqual(['no_go', 'go']); expect(two.latest?.note).toBe('Agreed at three weeks.'); expect(hasHistory(two)).toBe(true)
  })
  it('is a different list from Deploy\'s, so the two are never mixed up', () => {
    const deploy = decodeChecklist(deployList)
    expect(deploy.phase).toBe('deploy'); expect(list.phase).toBe('handover')
    expect(allChecks(list).some((c) => allChecks(deploy).some((d) => d.id === c.id || d.question === c.question))).toBe(false)
  })
})

describe('the sign-off in words', () => {
  it('names an answer in the sign-off\'s words, who answered it, and "Not answered" when it has not been', () => {
    const [one] = allChecks(list)
    expect(standing(one, list)).toBe('Accept'); expect(answeredBy(one)).toMatch(/^Demo Person · /); expect(standing(allChecks(blank)[0], blank)).toBe('Not answered')
    expect(wordFor(list, 'no_go')).toBe('Not accepted')
  })
  it('writes the headline with accept and not accepted, never go and no-go', () => {
    expect(headline(blank)).toBe('0 of 8 answered · no overall decision yet'); expect(headline(list)).toBe('4 of 8 answered · overall: Accept')
    const bad = clone(list); bad.totals.no_go = 2
    expect(headline(bad)).toBe('4 of 8 answered · 2 Not accepted · overall: Accept')
  })
})

describe('the panel', () => {
  it('shows the groups, the three choices for each statement in the sign-off\'s words, a note box, and the headline', () => {
    const out = panel(blank)
    for (const title of ['What support has been given', 'What support can do', 'The decision']) expect(out).toContain(`<h4 class="mb-1 text-sm font-bold">${title}</h4>`)
    expect((out.match(/aria-label="Answer for SGN-\d{3}"/g) ?? []).length).toBe(8); expect((out.match(/>Accept<\/button>/g) ?? []).length).toBe(8)
    expect((out.match(/>Not accepted<\/button>/g) ?? []).length).toBe(8); expect((out.match(/>Not applicable<\/button>/g) ?? []).length).toBe(8); expect((out.match(/aria-label="Note for SGN-\d{3}"/g) ?? []).length).toBe(8)
    expect(out).toContain('0 of 8 answered · no overall decision yet'); expect(out).toContain('aria-label="Handover sign-off"')
  })
  it('marks the chosen answer, shows who and when and the note, and the history of a changed mind', () => {
    const out = panel(list)
    const two = out.slice(out.indexOf('aria-label="SGN-002: Accept"'), out.indexOf('aria-label="SGN-003'))
    expect(two).toContain('aria-pressed="true"'); expect(two).toContain('Accept · Demo Person · '); expect(two).toContain('Agreed at three weeks.'); expect(two).toContain('Not accepted · ')
  })
  it('says nothing of Deploy, and its report links go to the handover addresses', () => {
    const out = panel(list)
    expect(out).not.toContain('Deployment'); expect(out).not.toContain('No-go'); expect(out).not.toContain('>Go<')
    expect(out).toContain('href="/api/projects/p1/handover/checklist/report?format=md"'); expect(out).toContain('href="/api/projects/p1/handover/checklist/report?format=docx"')
  })
  it('says a Not accepted does not stop approval, in the sign-off\'s own word', () => {
    const bad = clone(list); bad.totals.no_go = 1
    expect(panel(bad)).toContain('A Not accepted does not stop you approving the phase')
  })
})

describe('the fold', () => {
  it('is collapsible and starts open, with the title and progress in the summary so they stay in view when it is folded', () => {
    const out = panel(list)
    expect(out).toMatch(/<details open=""[^>]*class="group"><summary[^>]*><h3[^>]*>Handover sign-off<\/h3><span role="status"[^>]*>4 of 8 answered · overall: Accept<\/span><\/summary>/)
    expect((out.match(/<details open=""/g) ?? []).length).toBe(1)                                          // only the outer fold is open by default; a history fold stays shut
  })
  it('keeps every statement inside the fold, so folding it hides the whole list', () => {
    const out = panel(blank)
    const inside = out.slice(out.indexOf('</summary>'), out.lastIndexOf('</details>'))
    expect((inside.match(/aria-label="Answer for SGN-\d{3}"/g) ?? []).length).toBe(8)
  })
})

describe('the Handover page', () => {
  const project = decodeProject(detailJson)
  const page = (key: string, checklist: Checklist | null) => html(<ProjectPage project={project} phaseKey={key} screen={{ ...emptyScreen, checklist }} />)
  it('shows the sign-off beside the blue card, with the card showing its progress', () => {
    const out = page('handover', list)
    expect(out).toContain('aria-label="Handover sign-off"'); expect(out).toContain('aria-label="Handover sign-off: done by hand"'); expect(out).toContain('4 of 8 answered · overall: Accept')
    expect(out.indexOf('Hypercare plan')).toBeLessThan(out.indexOf('aria-label="Handover sign-off"'))
  })
  it('shows nothing of it until it has loaded, and never on another phase except Deploy\'s own list on Deploy', () => {
    expect(page('handover', null)).not.toContain('aria-label="Handover sign-off"><')
    for (const p of project.phases.filter((x) => x.key !== 'handover' && x.key !== 'deploy')) expect(page(p.key, list)).not.toContain('aria-label="Handover sign-off"')
  })
})

describe('the approval summary', () => {
  const open = (extra: Record<string, unknown>) => decodeOpenItems({ open_high_findings: 0, unreviewed: [], review_out_of_date: [], built_on_changed: [], guardrail_flags: {}, traceability_gaps: { needs_attention: 0, explained: 0, items: [] }, ...extra })
  it('counts the sign-off\'s open statements with Deploy\'s, and reads them from the record when it is there', () => {
    const o = open({ handover_signoff: { no_go: ['SGN-004'], unanswered: ['SGN-005', 'SGN-006'], decision: null } })
    expect(o.handover_signoff).toEqual({ no_go: ['SGN-004'], unanswered: ['SGN-005', 'SGN-006'], decision: null }); expect(openCount(o)).toBe(3)
    expect(openCount(open({}))).toBe(0)
    expect(openCount(open({ deployment_checks: { no_go: ['CHK-002'], unanswered: [], decision: null }, handover_signoff: { no_go: ['SGN-004'], unanswered: [], decision: 'go' } }))).toBe(2)
  })
  it('writes the line in the sign-off\'s own words', () => {
    expect(checksLine({ no_go: ['SGN-004'], unanswered: ['SGN-005', 'SGN-006'], decision: null }, SIGNOFF_WORDING))
      .toBe('Handover sign-off: 1 statement marked Not accepted (SGN-004); 2 statements not answered yet, and no overall Accept / Not accepted recorded')
    expect(checksLine({ no_go: [], unanswered: [], decision: 'go' }, SIGNOFF_WORDING)).toBeNull()
  })
  it('shows it in the summary before approving, pointing at the sign-off, and leaves Deploy\'s line as it was', () => {
    const out = html(<ApprovalSummary open={open({ handover_signoff: { no_go: ['SGN-004'], unanswered: [], decision: null } })} names={{}} />)
    expect(out).toContain('1 thing still open'); expect(out).toContain('Handover sign-off: 1 statement marked Not accepted (SGN-004), and no overall Accept / Not accepted recorded'); expect(out).toContain('(see the sign-off on this page)')
    const deploy = html(<ApprovalSummary open={open({ deployment_checks: { no_go: ['CHK-002'], unanswered: [], decision: 'go' } })} names={{}} />)
    expect(deploy).toContain('Deployment checklist: 1 check marked No-go (CHK-002)'); expect(deploy).toContain('(see the checklist on this page)'); expect(deploy).not.toContain('sign-off')
  })
  it('refuses a damaged record', () => {
    expect(() => open({ handover_signoff: { no_go: 'SGN-004', unanswered: [], decision: null } })).toThrow()
    expect(() => open({ handover_signoff: { no_go: [], unanswered: [], decision: 'maybe' } })).toThrow()
  })
})
