// S12c: the review chip and panel, the family picker, the send-back form, the edit view, the stale banner, the approval summary, and the
// project page with review state. Rendered to static HTML; what is asserted is what a person would see.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  decodeArtefactDetail, decodeArtefactList, decodeProject, decodeReviewAnswer, decodeReviewState, type OpenItems, type ReviewStatus, type StoredReview,
} from '../api'
import artefactsJson from '../contract/artefacts.json'
import detailJson from '../contract/project_detail.json'
import pausedJson from '../contract/review_paused.json'
import reviewDetailJson from '../contract/review_artefact_detail.json'
import stateAfterJson from '../contract/review_state_after.json'
import stateStaleJson from '../contract/review_state_stale.json'
import { actionSpecs } from '../lib/phaseActions'
import { emptyReview, emptyScreen, ProjectPage, type ReviewScreen } from '../pages/ProjectPage'
import { ApprovalSummary, openCount } from './ApprovalSummary'
import { ArtefactCardView } from './ArtefactCard'
import { ArtefactReader } from './ArtefactReader'
import { EditArtefact } from './EditArtefact'
import { FamilyPicker } from './FamilyPicker'
import { RequestChangesForm, emptyForm, formPayload, formProblem } from './RequestChangesForm'
import { IndependenceChip, ReviewChip } from './ReviewChip'
import { ReviewPanel, FindingRow } from './ReviewPanel'
import { CopyButton, COPY_LABEL } from './CopyButton'
import { StaleBanner } from './StaleBanner'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const tags = (out: string) => [...out.matchAll(/<([a-z][a-z0-9]*)\b/gi)].map((m) => m[1].toLowerCase())
const disabledButton = (label: string) => new RegExp(`<button[^>]*\\sdisabled=""[^>]*>(<svg[^>]*>.*?</svg> )?${label}`)
const buttons = (out: string) => [...out.matchAll(/<button[^>]*>(?:<svg[^>]*>.*?<\/svg> )?([^<]*)<\/button>/g)].map((m) => m[1].trim())

const detail = decodeProject(detailJson)
const cards = decodeArtefactList(artefactsJson)
const artefact = decodeArtefactDetail(reviewDetailJson)
const review = artefact.review as StoredReview
const state = decodeReviewState(stateAfterJson)
const staleState = decodeReviewState(stateStaleJson)
const paused = (() => { const p = decodeReviewAnswer(pausedJson); if (!p.paused) throw new Error('expected paused'); return p })()
const status = (over: Partial<ReviewStatus> = {}): ReviewStatus => ({ artefact_id: 'A', state: 'reviewed', verdict: 'ok', reviewed_version: 1, latest_version: 1, high_findings: 0, ...over })
const noGaps = { needs_attention: 0, explained: 0, items: [] as string[] }
const noOpen: OpenItems = { open_high_findings: 0, unreviewed: [], review_out_of_date: [], built_on_changed: [], guardrail_flags: {}, traceability_gaps: noGaps }

describe('the review chip', () => {
  it('not reviewed, with no status at all, reads the same', () => {
    expect(html(<ReviewChip status={null} />)).toContain('Not reviewed')
    expect(html(<ReviewChip status={status({ state: 'unreviewed', verdict: null })} />)).toContain('Not reviewed')
  })
  it('OK and Revise are different words, with the number of high findings', () => {
    expect(html(<ReviewChip status={status()} />)).toContain('>OK<')
    const revise = html(<ReviewChip status={status({ verdict: 'revise', high_findings: 2 })} />)
    expect(revise).toContain('Revise · 2 high')
    expect(revise).not.toContain('>OK<')
  })
  it('a review of an older version says so and names the version it covers', () => {
    const out = html(<ReviewChip status={status({ state: 'stale', reviewed_version: 1, latest_version: 2 })} />)
    expect(out).toContain('Review out of date (covers v1)')
  })
  it('the three independence labels are three different words', () => {
    const words = ['independent', 'same_family', 'unverified'].map((l) => html(<IndependenceChip label={l} />))
    expect(words[0]).toContain('>Independent<'); expect(words[1]).toContain('>Same family<'); expect(words[2]).toContain('>Unverified<')
    expect(new Set(words).size).toBe(3)
  })
  it('the colours differ too: only "independent" is green, "same family" is amber, "unverified" is grey', () => {
    const green = (out: string) => out.includes('emerald')
    expect(green(html(<IndependenceChip label="independent" />))).toBe(true)
    expect(green(html(<IndependenceChip label="same_family" />))).toBe(false)
    expect(html(<IndependenceChip label="same_family" />)).toContain('amber')
    expect(green(html(<IndependenceChip label="unverified" />))).toBe(false)
    expect(html(<IndependenceChip label="unverified" />)).toContain('slate')
  })
  it('an unknown label is shown as unverified, never as independent', () => {
    const out = html(<IndependenceChip label="something_new" />)
    expect(out).toContain('>Unverified<')
    expect(out).not.toContain('Independent')
  })
})

describe('the review panel', () => {
  it('shows the verdict, the independence in words, the summary and the cost', () => {
    const out = html(<ReviewPanel review={review} shownVersion={review.version_reviewed} />)
    expect(out).toContain('>Revise<')
    expect(out).toContain('Same family')
    expect(out).toContain('the same model family as the writer: a second look, not an independent one')
    expect(out).toContain(review.summary)
    expect(out).toContain('cost $')
  })
  it('groups findings by severity, highest first, each with its target, problem and fix', () => {
    const out = html(<ReviewPanel review={review} shownVersion={review.version_reviewed} />)
    expect(out.indexOf('High (')).toBeGreaterThan(-1)
    expect(out.indexOf('High (')).toBeLessThan(out.indexOf('Low ('))
    expect(out).not.toContain('Medium (')                                  // a group with nothing in it is not shown
    expect(out).toContain('Suggested fix:')
    expect(out).toContain(review.findings[0].target)
  })
  it('a review that covers an older version says so', () => {
    expect(html(<ReviewPanel review={review} shownVersion={review.version_reviewed + 1} />)).toContain(`covers version ${review.version_reviewed}`)
    expect(html(<ReviewPanel review={review} shownVersion={review.version_reviewed} />)).not.toContain('covers version')
  })
  it('no findings says so', () => {
    expect(html(<ReviewPanel review={{ ...review, findings: [], verdict: 'ok' }} shownVersion={review.version_reviewed} />)).toContain('No findings.')
  })
  it('a fallback model is mentioned, and a reviewer that needed corrections is disclosed', () => {
    const out = html(<ReviewPanel review={{ ...review, independence: { ...review.independence, fell_back: true }, repair_reasons: [{ attempt: 1, problems: ['a finding named an item that is not in the artefact'] }] }} shownVersion={review.version_reviewed} />)
    expect(out).toContain('a fallback model answered')
    expect(out).toContain('needed 1 correction before this was accepted')
    expect(out).toContain('a finding named an item that is not in the artefact')
  })
  it('every word the model wrote is text, never markup', () => {
    const evil = { ...review, summary: '<script>x()</script>', findings: [{ severity: 'high' as const, target: '<img src=x onerror=1>', problem: '<b onmouseover=1>bad</b>', fix: '<i>fix</i>' }] }
    const out = html(<ReviewPanel review={evil} shownVersion={review.version_reviewed} />)
    expect(tags(out)).not.toContain('script'); expect(tags(out)).not.toContain('img'); expect(tags(out)).not.toContain('b'); expect(tags(out)).not.toContain('i')
    expect(out).toContain('&lt;script&gt;')
  })
  it('an unknown cost reads unknown, never $0.00', () => {
    const out = html(<ReviewPanel review={{ ...review, cost_usd: null }} shownVersion={review.version_reviewed} />)
    expect(out).toContain('cost unknown')
    expect(out).not.toContain('$0.00')
  })
})

describe('the artefact reader with review and edit', () => {
  const props = { artefact, onClose: noop, onVersion: noop }
  it('shows the stored review under the text', () => {
    const out = html(<ArtefactReader {...props} />)
    expect(out.indexOf('aria-label="Review"')).toBeGreaterThan(out.indexOf('class="markdown"'))
  })
  it('offers Review, Review again and Edit only when allowed, and only on the latest version', () => {
    expect(buttons(html(<ArtefactReader {...props} />))).not.toContain('Review this artefact')
    expect(buttons(html(<ArtefactReader {...props} canReview />))).toContain('Review again')                      // it already has a review
    expect(buttons(html(<ArtefactReader {...props} artefact={{ ...artefact, review: null }} canReview />))).toContain('Review this artefact')
    expect(buttons(html(<ArtefactReader {...props} canEdit />))).toContain('Edit by hand')
    const older = html(<ArtefactReader {...props} artefact={{ ...artefact, is_latest: false }} canReview canEdit />)
    expect(buttons(older)).not.toContain('Edit by hand'); expect(buttons(older)).not.toContain('Review again')
  })
  it('while reviewing the button says so and is off', () => {
    expect(html(<ArtefactReader {...props} canReview reviewBusy />)).toMatch(disabledButton('Reviewing…'))
  })
  it('in replay mode the one sentence replaces the button', () => {
    const out = html(<ArtefactReader {...props} reviewNote="Reviews need live mode: no review has been recorded yet." />)
    expect(out).toContain('Reviews need live mode')
    expect(buttons(out)).not.toContain('Review this artefact')
  })
})

describe('the family picker', () => {
  const props = { slot: paused.slot, options: paused.options, chosen: null, busy: false, onChoose: noop, onReview: noop }
  it('says which reviewer could not run, and lists the other families with model and price', () => {
    const out = html(<FamilyPicker {...props} />)
    expect(out).toContain('The sonnet reviewer could not run. Choose another model family to review with.')
    for (const o of paused.options) { expect(out).toContain(o.family); expect(out).toContain(o.model_id) }
    expect(out.match(/type="radio"/g)).toHaveLength(paused.options.length)
  })
  it('an unpriced option says unknown and that no price is set, never $0.00', () => {
    const out = html(<FamilyPicker {...props} />)
    expect(paused.options.some((o) => !o.priced)).toBe(true)                // precondition
    expect(out).toContain('input unknown · output unknown per million tokens (no price set)')
    expect(out).not.toContain('$0.00')
  })
  it('a priced option shows its prices', () => {
    const out = html(<FamilyPicker {...props} options={[{ slot: 'openai', model_id: 'gpt-x', family: 'openai', independent: true, price_input: 2, price_output: 10, priced: true }]} />)
    expect(out).toContain('input $2.00 · output $10 per million tokens')
    expect(out).not.toContain('no price set')
  })
  it('independence is stated three ways', () => {
    const mk = (independent: boolean | null) => html(<FamilyPicker {...props} options={[{ slot: 's', model_id: 'm', family: 'f', independent, price_input: null, price_output: null, priced: false }]} />)
    expect(mk(true)).toContain('independent of the writer'); expect(mk(false)).toContain('same family as the writer'); expect(mk(null)).toContain('independence unverified')
  })
  it('nothing is chosen for the person: the button is off until they choose, then on', () => {
    expect(html(<FamilyPicker {...props} />)).toMatch(disabledButton('Review with the chosen family'))
    expect(html(<FamilyPicker {...props} chosen={paused.options[0].slot} />)).not.toMatch(disabledButton('Review with the chosen family'))
    expect(html(<FamilyPicker {...props} chosen={paused.options[0].slot} />).match(/checked=""/g)).toHaveLength(1)
    expect(html(<FamilyPicker {...props} />)).not.toContain('checked=""')
  })
  it('while reviewing it says so and is off', () => { expect(html(<FamilyPicker {...props} chosen="x" busy />)).toMatch(disabledButton('Reviewing…')) })
  it('with no other family it says so instead of showing an empty list', () => {
    const out = html(<FamilyPicker {...props} options={[]} />)
    expect(out).toContain('No other model family is configured')
    expect(out).not.toContain('type="radio"')
  })
})

describe('the send-back form', () => {
  const rows = [{ id: 'REQ-PER-001', name: 'Personas', hasReview: true }, { id: 'REQ-F-001', name: 'Functional requirements', hasReview: false }]
  const base = { rows, busy: false, error: null, onSend: noop, onCancel: noop }
  it('lists every written artefact with a tick box, and no note boxes until one is ticked', () => {
    const out = html(<RequestChangesForm {...base} />)
    expect(out).toContain('Send back: Personas'); expect(out).toContain('Send back: Functional requirements')
    expect(out).not.toContain('What to change in')
    expect(buttons(out)).toContain('Send back'); expect(out).toMatch(disabledButton('Send back'))
  })
  it('the rules: nothing ticked, a tick with no note, a note over the limit', () => {
    expect(formProblem(emptyForm)).toBe('Tick at least one artefact to send back.')
    expect(formProblem({ ...emptyForm, ticked: { a: true } })).toContain('needs a note')
    expect(formProblem({ ...emptyForm, ticked: { a: true }, notes: { a: '   ' } })).toContain('needs a note')
    expect(formProblem({ ...emptyForm, ticked: { a: true }, notes: { a: 'fix it' } })).toBeNull()
    expect(formProblem({ ...emptyForm, ticked: { a: true }, notes: { a: 'x'.repeat(4001) } })).toContain('limited to 4000')
    expect(formProblem({ ...emptyForm, ticked: { a: true }, notes: { a: 'ok' }, overall: 'y'.repeat(4001) })).toContain('limited to 4000')
  })
  it('an unticked artefact is not sent, even if it has a note', () => {
    const payload = formPayload({ ticked: { a: true, b: false }, notes: { a: ' fix a ', b: 'stale text' }, findings: { a: true, b: true }, overall: ' whole ' })
    expect(payload).toEqual({ notes: { a: 'fix a' }, overall: 'whole', include_findings: ['a'] })
  })
  it('a server refusal is shown as text and the cancel button is there', () => {
    const out = html(<RequestChangesForm {...base} error="<b>Personas</b> is not in this phase" />)
    expect(out).toContain('The changes were not sent'); expect(out).toContain('&lt;b&gt;Personas'); expect(tags(out)).not.toContain('b')
    expect(buttons(out)).toContain('Cancel')
  })
  it('while sending both buttons are off', () => {
    const out = html(<RequestChangesForm {...base} busy />)
    expect(out).toMatch(disabledButton('Sending…')); expect(out).toMatch(disabledButton('Cancel'))
  })
})

describe('the edit view', () => {
  const props = { title: 'Personas', initialBody: '## Overview\nHello', busy: false, refusal: null, error: null, onSave: noop, onCancel: noop }
  it('shows the stored Markdown in a plain text area, and says what the checks are', () => {
    const out = html(<EditArtefact {...props} />)
    expect(out).toContain('<textarea'); expect(out).toContain('## Overview\nHello')
    expect(out).toContain('every check an agent&#x27;s text passes')
  })
  it('Save is off while nothing has changed', () => { expect(html(<EditArtefact {...props} />)).toMatch(disabledButton('Save as a new version')) })
  it('a refusal lists every reason and says the text is kept', () => {
    const out = html(<EditArtefact {...props} refusal={{ message: 'the edit was not saved: 2 problems', problems: ['the section &quot;Personas&quot; is missing', 'FR-099 is not an item'] }} />)
    expect(out).toContain('Not saved'); expect(out).toContain('the edit was not saved: 2 problems'); expect(out).toContain('FR-099 is not an item')
    expect(out.match(/<li>/g)).toHaveLength(2)
    expect(out).toContain('Your text is still in the box')
  })
  it('the reasons are text, not markup', () => {
    const out = html(<EditArtefact {...props} refusal={{ message: 'm', problems: ['<script>x()</script>'] }} />)
    expect(tags(out)).not.toContain('script'); expect(out).toContain('&lt;script&gt;')
  })
  it('a plain error (not a list of reasons) is shown once, and not alongside a refusal', () => {
    expect(html(<EditArtefact {...props} error="the project is archived" />)).toContain('the project is archived')
    const both = html(<EditArtefact {...props} error="a plain error" refusal={{ message: 'refused', problems: ['one'] }} />)
    expect(both).toContain('refused'); expect(both).not.toContain('a plain error')
  })
  it('while saving, both buttons are off', () => {
    const out = html(<EditArtefact {...props} busy />)
    expect(out).toMatch(disabledButton('Saving…')); expect(out).toMatch(disabledButton('Cancel'))
  })
})

describe('the stale banner', () => {
  const names = { 'REQ-PER-001': 'Personas', 'REQ-F-001': 'Functional requirements' }
  const item = { artefact_id: 'REQ-F-001', version: 1, built_on: { 'REQ-PER-001': 1, 'REQ-PRB-001': 1 }, now: { 'REQ-PER-001': 2 } }
  it('shows nothing when nothing is stale', () => { expect(html(<StaleBanner stale={[]} names={names} busy={false} canChange onRerun={noop} />)).toBe('') })
  it('says what was built on what, and what it is now, naming only what moved', () => {
    const out = html(<StaleBanner stale={[item]} names={names} busy={false} canChange onRerun={noop} />)
    expect(out).toContain('1 artefact built on something that has changed')
    expect(out).toContain('Functional requirements was built on Personas v1; now Personas is v2')
    expect(out).not.toContain('REQ-PRB-001 v1')                      // what did NOT move is not listed
  })
  it('says the button takes the phase back to running, and that nothing happens by itself', () => {
    const out = html(<StaleBanner stale={[item]} names={names} busy={false} canChange onRerun={noop} />)
    expect(out).toContain('takes the phase back to running, as you'); expect(out).toContain('Nothing is re-run unless you press the button')
    expect(buttons(out)).toContain('Re-run these')
  })
  it('the button is off while busy or without a name', () => {
    expect(html(<StaleBanner stale={[item]} names={names} busy canChange onRerun={noop} />)).toMatch(disabledButton('Starting…'))
    expect(html(<StaleBanner stale={[item]} names={names} busy={false} canChange={false} onRerun={noop} />)).toMatch(disabledButton('Re-run these'))
  })
  it('the real fixture from the server renders', () => {
    expect(staleState.stale.length).toBeGreaterThan(0)
    expect(html(<StaleBanner stale={staleState.stale} names={{}} busy={false} canChange onRerun={noop} />)).toContain('built on something that has changed')
  })
})

describe('the approval summary', () => {
  const names = { 'REQ-PER-001': 'Personas', 'REQ-F-001': 'Functional requirements' }
  it('nothing open says so, and counts as zero', () => {
    expect(html(<ApprovalSummary open={noOpen} names={names} />)).toContain('Before you approve: nothing is open.')
    expect(openCount(noOpen)).toBe(0)
  })
  it('lists each kind of open thing by name, and says approving is still allowed', () => {
    const open: OpenItems = { open_high_findings: 2, unreviewed: ['REQ-F-001'], review_out_of_date: ['REQ-PER-001'], built_on_changed: ['REQ-F-001'], guardrail_flags: { 'REQ-PER-001': { email: 2 } }, traceability_gaps: noGaps }
    const out = html(<ApprovalSummary open={open} names={names} />)
    expect(out).toContain('2 high findings'); expect(out).toContain('Never reviewed: Functional requirements'); expect(out).toContain('Review out of date')
    expect(out).toContain('Built on something that has since changed'); expect(out).toContain('Personas carries flagged personal data: 2 times an email address')
    expect(out).toContain('Approving is still allowed')
    expect(openCount(open)).toBe(2 + 1 + 1 + 1 + 1)
  })
  it('after approving it says "Recorded when this phase was approved" and drops the invitation', () => {
    const out = html(<ApprovalSummary open={{ ...noOpen, unreviewed: ['REQ-F-001'] }} names={names} recorded />)
    expect(out).toContain('Recorded when this phase was approved'); expect(out).not.toContain('Approving is still allowed'); expect(out).not.toContain('Before you approve')
  })
  it('an artefact with no known name is shown by its ID, never as undefined', () => {
    const out = html(<ApprovalSummary open={{ ...noOpen, unreviewed: ['X-001'] }} names={{}} />)
    expect(out).toContain('X-001'); expect(out).not.toContain('undefined')
  })
  it('the real fixture from the server renders', () => { expect(html(<ApprovalSummary open={state.open} names={{}} />)).toContain('approve') })
})

describe('the project page with review state', () => {
  const review = (over: Partial<ReviewScreen> = {}): ReviewScreen => ({ ...emptyReview, state, available: true, ...over })
  const awaiting = { ...detail, phases: detail.phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'awaiting_review' as const, allowed_actions: ['approve' as const, 'request_changes' as const] } : p)) }
  const written = cards.map((c) => ({ ...c, phase_key: 'requirements' }))
  const screen = (r: ReviewScreen) => ({ ...emptyScreen, cards: written, review: r })

  it('a phase under review offers Review all, with a sentence that it costs money and never happens by itself', () => {
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review())} />)
    expect(buttons(out)).toContain('Review all'); expect(out).toContain('costs money; it never happens by itself')
  })
  it('in replay mode the button is replaced by the server\'s sentence', () => {
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review({ available: false, state: { ...state, reviews_available: false, replay_sentence: 'Reviews need live mode: no review has been recorded yet.' } }))} />)
    expect(buttons(out)).not.toContain('Review all'); expect(out).toContain('Reviews need live mode')
  })
  it('a phase that is not running or under review shows no review controls at all', () => {
    expect(html(<ProjectPage project={detail} phaseKey="setup" screen={screen(review())} />)).not.toContain('Review all')
  })
  it('each written artefact shows where its review stands', () => {
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review())} />)
    expect(out).toMatch(/Reviewed|>OK<|Revise|Not reviewed/)
  })
  it('the picker appears when a reviewer could not run, and not otherwise', () => {
    expect(html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review({ paused }))} />)).toContain('Choose another model family')
    expect(html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review())} />)).not.toContain('Choose another model family')
  })
  it('a review error is shown as text', () => {
    expect(html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review({ error: '<i>boom</i>' }))} />)).toContain('&lt;i&gt;boom')
  })
  it('the approval summary shows before approving, and "Approve anyway" when something is open', () => {
    const open = { ...noOpen, unreviewed: ['REQ-PER-001'] }
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review({ state: { ...state, open } }))} />)
    expect(out).toContain('Before you approve'); expect(buttons(out)).toContain('Approve anyway')
    const clean = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review({ state: { ...state, open: noOpen } }))} />)
    expect(buttons(clean)).toContain('Approve'); expect(buttons(clean)).not.toContain('Approve anyway')
  })
  it('after approving, the same list is shown as what was recorded', () => {
    const approved = { ...detail, phases: detail.phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'approved' as const, allowed_actions: [] } : p)) }
    const out = html(<ProjectPage project={approved} phaseKey="requirements" screen={screen(review({ state: { ...state, open: { ...noOpen, unreviewed: ['REQ-PER-001'] } } }))} />)
    expect(out).toContain('Recorded when this phase was approved')
  })
  it('the stale banner is shown while the phase can still change, and not once it is approved', () => {
    const r = review({ state: staleState })
    expect(html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(r)} />)).toContain('built on something that has changed')
    const approved = { ...detail, phases: detail.phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'approved' as const, allowed_actions: [] } : p)) }
    expect(html(<ProjectPage project={approved} phaseKey="requirements" screen={screen(r)} />)).not.toContain('Re-run these')
  })
  it('the send-back form appears when asked for, with a row per written artefact', () => {
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review({ sendingBack: true }))} />)
    expect(out).toContain('Send back for changes'); expect(out.match(/Send back: /g)!.length).toBe(cards.length)
    expect(html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review())} />)).not.toContain('Send back for changes')
  })
  it('a sent-back phase offers to rewrite exactly the artefacts with a note, by count', () => {
    const rejected = { ...detail, phases: detail.phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'rejected' as const, allowed_actions: ['run' as const] } : p)) }
    const out = html(<ProjectPage project={rejected} phaseKey="requirements" screen={screen(review({ state: { ...state, artefacts_with_notes: ['REQ-PER-001', 'REQ-F-001'] } }))} />)
    expect(buttons(out)).toContain('Rewrite the 2 sent back')
    expect(buttons(html(<ProjectPage project={rejected} phaseKey="requirements" screen={screen(review())} />))).toContain('Run it again')
  })
  it('the edit view replaces the reader while editing', () => {
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={{ ...screen(review({ editing: true })), open: artefact }} />)
    expect(out).toContain(`aria-label="Edit ${artefact.title}"`); expect(out).not.toContain('aria-label="Sources"')
  })
  it('the reader offers Review and Edit when the server allows them, and Edit is off while a run is going', () => {
    const open = { ...screen(review()), open: artefact }
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={open} />)
    expect(buttons(out)).toContain('Review again'); expect(buttons(out)).toContain('Edit by hand')
    expect(buttons(html(<ProjectPage project={awaiting} phaseKey="requirements" screen={{ ...open, runLive: true }} />))).not.toContain('Edit by hand')
  })
  it('without a name nothing that changes anything can be pressed', () => {
    const out = html(<ProjectPage project={awaiting} phaseKey="requirements" screen={screen(review())} canChange={false} />)
    expect(out).toMatch(disabledButton('Review all')); expect(out).toMatch(disabledButton('Approve'))
  })
})

describe('what each button says, with review state', () => {
  const phase = { ...detail.phases[1], status: 'awaiting_review' as const, allowed_actions: ['approve' as const, 'request_changes' as const] }
  it('the labels', () => {
    expect(actionSpecs(phase, 'live', 0).map((s) => s.label)).toEqual(['Approve', 'Request changes'])
    expect(actionSpecs(phase, 'live', 1).map((s) => s.label)).toEqual(['Approve anyway', 'Request changes'])
  })
  it('a replay-mode hint on run is unchanged by review state', () => {
    expect(actionSpecs({ ...phase, status: 'not_started', allowed_actions: ['run'] }, 'replay')[0].hint).toBe('Answers come from recordings: free and offline.')
  })
  it('the card for a written artefact shows its review chip only when the status is known', () => {
    const card = cards[0]
    expect(html(<ul><ArtefactCardView name="X" card={card} selected={false} onOpen={noop} /></ul>)).not.toContain('Not reviewed')
    expect(html(<ul><ArtefactCardView name="X" card={card} selected={false} onOpen={noop} review={null} /></ul>)).toContain('Not reviewed')
  })
})

// ---- the visible queue behind "Review all" ---------------------------------------------------------------------------------------------------

import { ReviewProgress } from './ReviewProgress'
import { finishRun, markDone, markFailed, markPaused, markReviewing, requestStop, startRun } from '../state/reviewQueue'

describe('the review progress list', () => {
  const q = [{ id: 'A', name: 'Personas' }, { id: 'B', name: 'Problem statement' }, { id: 'C', name: 'Vision' }]
  const answer = (id: string, over: Record<string, unknown> = {}) => ({
    paused: false as const, artefact_id: id, version: 1, verdict: 'ok' as const, summary: 's', findings: [],
    independence: { label: 'independent' as const, author_family: 'a', reviewer_family: 'b', fell_back: false }, cost_usd: 0.012, attempts: 1, ...over,
  })
  const midway = () => markReviewing(markDone(markReviewing(startRun(q), 'A'), 'A', answer('A')), 'B')

  it('shows a row per artefact with where each one is, and a count that climbs', () => {
    const out = html(<ReviewProgress run={midway()} onStop={noop} onDismiss={noop} />)
    expect(out).toContain('Reviewing 2 of 3')
    for (const n of ['Personas', 'Problem statement', 'Vision']) expect(out).toContain(n)
    expect(out).toContain('Done'); expect(out).toContain('Reviewing'); expect(out).toContain('Waiting')
    expect(out).toContain('<progress')
  })
  it('a finished review shows its verdict, independence and cost on its own row, the moment it is ready', () => {
    const out = html(<ReviewProgress run={markDone(startRun(q), 'A', answer('A', { verdict: 'revise', findings: [{ severity: 'high', target: 't', problem: 'p', fix: 'f' }] }) as never)} onStop={noop} onDismiss={noop} />)
    expect(out).toContain('Revise · 1 high finding'); expect(out).toContain('Independent'); expect(out).toContain('$0.0120')
  })
  it('a running queue has a Stop button, and after asking it says it is stopping and turns the button off', () => {
    expect(buttons(html(<ReviewProgress run={midway()} onStop={noop} onDismiss={noop} />))).toContain('Stop after this one')
    const stopping = html(<ReviewProgress run={requestStop(midway())} onStop={noop} onDismiss={noop} />)
    expect(stopping).toContain('Stopping after this one'); expect(stopping).toMatch(disabledButton('Stopping…'))
  })
  it('a finished queue has Dismiss and no Stop, and no progress bar', () => {
    const out = html(<ReviewProgress run={finishRun(midway(), 'you')} onStop={noop} onDismiss={noop} />)
    expect(buttons(out)).toContain('Dismiss'); expect(buttons(out)).not.toContain('Stop after this one'); expect(out).not.toContain('<progress')
    expect(out).toContain('Stopped: 1 of 3 reviewed'); expect(out).toContain('You stopped before this one.')
  })
  it('a paused queue says a reviewer is needed and which row is waiting for it', () => {
    const out = html(<ReviewProgress run={finishRun(markPaused(markReviewing(startRun(q), 'A'), 'A'), 'paused')} onStop={noop} onDismiss={noop} />)
    expect(out).toContain('Paused after 0 of 3: a reviewer is needed'); expect(out).toContain('Needs a reviewer'); expect(out).toContain('choose another model family below')
    expect(out).toContain('Waiting for you to choose a reviewer.')
  })
  it('a failed review shows the server\'s sentence as text', () => {
    const out = html(<ReviewProgress run={finishRun(markFailed(markReviewing(startRun(q), 'A'), 'A', '<b>the reply failed its checks</b>'), 'problem')} onStop={noop} onDismiss={noop} />)
    expect(out).toContain('Failed'); expect(out).toContain('&lt;b&gt;the reply failed'); expect(tags(out)).not.toContain('b')
    expect(out).toContain('Not run: an earlier problem stopped the queue.')
  })
  it('cost so far is a number while every review was priced, and unknown (not zero) once one was not', () => {
    expect(html(<ReviewProgress run={markDone(startRun(q), 'A', answer('A'))} onStop={noop} onDismiss={noop} />)).toContain('Cost so far $0.0120')
    const unpriced = html(<ReviewProgress run={markDone(startRun(q), 'A', answer('A', { cost_usd: null }))} onStop={noop} onDismiss={noop} />)
    expect(unpriced).toContain('unknown (a review had no price)'); expect(unpriced).not.toContain('$0.00')
  })
  it('an artefact name with markup is text', () => {
    const out = html(<ReviewProgress run={startRun([{ id: 'X', name: '<img src=x onerror=1>' }])} onStop={noop} onDismiss={noop} />)
    expect(tags(out)).not.toContain('img'); expect(out).toContain('&lt;img')
  })
})

describe('Review all on the project page', () => {
  const awaiting = { ...detail, phases: detail.phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'awaiting_review' as const, allowed_actions: ['approve' as const, 'request_changes' as const] } : p)) }
  const written = cards.map((c) => ({ ...c, phase_key: 'requirements' }))
  const page = (r: Partial<ReviewScreen>) => html(<ProjectPage project={awaiting} phaseKey="requirements" screen={{ ...emptyScreen, cards: written, review: { ...emptyReview, state, available: true, ...r } }} />)

  it('shows the queue while reviews run, in place of the generic note, and no other progress indicator is needed', () => {
    const run = markReviewing(startRun(written.map((c) => ({ id: c.id, name: c.title }))), written[0].id)
    const out = page({ run, busy: 'phase' })
    expect(out).toContain('aria-label="Review progress"'); expect(out).toContain(`Reviewing 1 of ${written.length}`)
    expect(out).not.toContain('it never happens by itself')
  })
  it('without a queue it shows the explanation, and no queue', () => {
    const out = page({})
    expect(out).toContain('it never happens by itself'); expect(out).not.toContain('aria-label="Review progress"')
  })
  it('Review all is off while the queue is going', () => {
    expect(page({ run: startRun([{ id: 'A', name: 'A' }]), busy: 'phase' })).toMatch(disabledButton('Reviewing…'))
  })
  it('the picker shows under the paused queue, so the choice is next to the row that needs it', () => {
    const run = finishRun(markPaused(markReviewing(startRun([{ id: 'A', name: 'A' }]), 'A'), 'A'), 'paused')
    const out = page({ run, paused })
    expect(out.indexOf('aria-label="Review progress"')).toBeLessThan(out.indexOf('Choose another model family'))
  })
})

// ---- reopening an approved phase ---------------------------------------------------------------------------------------------------------

import { ReopenForm, MAX_REASON, reasonProblem, submitReopen, laterStartedNames } from './ReopenForm'
import { pressRoute } from '../lib/phaseActions'
import { makeClient } from '../api'
import { decodeGate, decodeError } from '../api'
import gateReopen from '../contract/gate_reopen.json'
import errorBlank from '../contract/error_422_reopen_blank.json'
import errorNotApproved from '../contract/error_409_reopen_not_approved.json'

describe('the reopen answers from the server', () => {
  it('a reopened phase is running with no decision', () => {
    expect(decodeGate(gateReopen)).toEqual({ phase: 'setup', status: 'running', decision: null, decided_by: null })
  })
  it('the two refusals are plain sentences', () => {
    expect(decodeError(errorBlank)).toContain('say why you are reopening this phase')
    expect(decodeError(errorNotApproved)).toContain('only an approved phase can be reopened')
  })
})

describe('the reason', () => {
  it.each([['', true], ['   ', true], ['\n\t ', true], ['x', false], ['  a  b  ', false], ['r'.repeat(MAX_REASON), false], ['r'.repeat(MAX_REASON + 1), true]] as const)('%j is a problem: %s', (reason, problem) => {
    expect(reasonProblem(reason) !== null).toBe(problem)
  })
  it('says what to do, and what the limit is', () => {
    expect(reasonProblem('')).toBe('Say why you are reopening this phase.')
    expect(reasonProblem('r'.repeat(MAX_REASON + 1))).toBe(`Keep the reason to ${MAX_REASON} characters or fewer.`)
  })
  it('whitespace between words does not count toward the limit', () => {
    expect(reasonProblem('a' + ' '.repeat(5000) + 'b')).toBeNull()
  })
})

describe('the reopen form', () => {
  const props = { phaseName: 'Design', busy: false, error: null, laterStarted: [] as string[], onReopen: noop, onCancel: noop }
  it('names the phase, says what happens and that approval is cleared, and asks for a reason recorded with the name', () => {
    const out = html(<ReopenForm {...props} />)
    expect(out).toContain('Reopen Design?'); expect(out).toContain('goes back to running'); expect(out).toContain('need approving again')
    expect(out).toContain('Why? (recorded with your name)'); expect(out).toContain('<textarea')
  })
  it('with no later phase started it says nothing else is affected', () => {
    expect(html(<ReopenForm {...props} />)).toContain('No later phase has started, so nothing else is affected.')
  })
  it('with later phases started it names them and says they are not changed but will be flagged', () => {
    const one = html(<ReopenForm {...props} laterStarted={['Architecture']} />)
    expect(one).toContain('<strong>Architecture</strong> is not changed'); expect(one).toContain('it shows'); expect(one).not.toContain('No later phase')
    const two = html(<ReopenForm {...props} laterStarted={['Architecture', 'Build & Test']} />)
    expect(two).toContain('Architecture, Build &amp; Test</strong> are not changed'); expect(two).toContain('they show')
  })
  it('Reopen is off until there is a reason, and Cancel is there', () => {
    const out = html(<ReopenForm {...props} />)
    expect(out).toMatch(disabledButton('Reopen')); expect(buttons(out)).toContain('Cancel')
  })
  it('while reopening both buttons are off and say so', () => {
    const out = html(<ReopenForm {...props} busy />)
    expect(out).toMatch(disabledButton('Reopening…')); expect(out).toMatch(disabledButton('Cancel'))
  })
  it('a refusal from the server is text', () => {
    const out = html(<ReopenForm {...props} error="<b>Design</b> is running" />)
    expect(out).toContain('It was not reopened'); expect(out).toContain('&lt;b&gt;Design'); expect(tags(out)).not.toContain('b')
  })
  it('a phase name with markup is text', () => {
    const out = html(<ReopenForm {...props} phaseName="<img src=x onerror=1>" laterStarted={['<script>x()</script>']} />)
    expect(tags(out)).not.toContain('img'); expect(tags(out)).not.toContain('script')
  })
})

describe('the Reopen button on an approved phase', () => {
  const approved = (key: string, over = {}) => ({ ...detail, phases: detail.phases.map((p) => (p.key === key ? { ...p, status: 'approved' as const, decided_by: 'human:Ann', allowed_actions: ['reopen' as const], ...over } : p)) })
  const page = (project: typeof detail, r: Partial<ReviewScreen> = {}, key = 'requirements') => html(<ProjectPage project={project} phaseKey={key} screen={{ ...emptyScreen, cards: written, review: { ...emptyReview, state, available: true, ...r } }} />)
  const written = cards.map((c) => ({ ...c, phase_key: 'requirements' }))

  it('an approved phase shows Reopen with a sentence saying what it does, instead of "Nothing to do here right now"', () => {
    const out = page(approved('requirements'))
    expect(buttons(out)).toContain('Reopen'); expect(out).not.toContain('Nothing to do here right now')
    expect(out).toContain('Phases after it are not changed')
  })
  it('it works for every phase, because the server decides: any approved phase with that action shows it', () => {
    for (const key of detail.phases.map((p) => p.key)) expect(buttons(page(approved(key), {}, key)), key).toContain('Reopen')
  })
  it('a phase that is not approved shows no Reopen', () => {
    expect(buttons(page(detail, {}, 'setup'))).not.toContain('Reopen')
  })
  it('the form replaces nothing else and appears when asked for', () => {
    const out = page(approved('requirements'), { reopening: true })
    expect(out).toContain('Reopen Requirements?'); expect(out).toContain('aria-label="Reopen Requirements"')
    expect(page(approved('requirements'))).not.toContain('Reopen Requirements?')
  })
  it('the form names the later phases that are under way or approved, and not the ones that never started', () => {
    const project = { ...approved('setup'), phases: approved('setup').phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'approved' as const } : p.key === 'design' ? { ...p, status: 'running' as const } : p)) }
    const out = page(project, { reopening: true }, 'setup')
    expect(out).toContain('<strong>Requirements, Design</strong> are not changed'); expect(out).not.toContain('Architecture</strong>')
  })
  it('without a name it cannot be pressed', () => {
    expect(html(<ProjectPage project={approved('requirements')} phaseKey="requirements" canChange={false} screen={{ ...emptyScreen, review: { ...emptyReview, state } }} />)).toMatch(disabledButton('Reopen'))
  })
  it('a later phase that stands on a reopened one keeps showing its review flag in the rail', () => {
    const project = approved('requirements', { needs_review: true })
    expect(page(project)).toContain('>review<')
  })
  it('after reopening, the phase offers Run and Hand to review again, as the server says', () => {
    const running = { ...detail, phases: detail.phases.map((p) => (p.key === 'requirements' ? { ...p, status: 'running' as const, allowed_actions: ['run' as const, 'finish' as const] } : p)) }
    const labels = buttons(page(running))
    expect(labels).toContain('Hand to review'); expect(labels).not.toContain('Reopen')
  })
})


describe('Reopen: the pieces that decide what happens', () => {
  it('the reason limit is 1000, the same number the server enforces (a literal, so a changed constant cannot hide)', () => {
    expect(MAX_REASON).toBe(1000)
    expect(reasonProblem('r'.repeat(1000))).toBeNull(); expect(reasonProblem('r'.repeat(1001))).not.toBeNull()
  })
  it('pressing Reopen sends the reason only when it passes, and says whether it did', () => {
    const sent: string[] = []
    expect(submitReopen('   ', (r) => sent.push(r))).toBe(false)
    expect(submitReopen('r'.repeat(1001), (r) => sent.push(r))).toBe(false)
    expect(sent).toEqual([])
    expect(submitReopen('the brief changed', (r) => sent.push(r))).toBe(true)
    expect(sent).toEqual(['the brief changed'])
  })
  const phases = [
    { name: 'Setup', order: 1, status: 'approved' }, { name: 'Requirements', order: 2, status: 'approved' }, { name: 'Design', order: 3, status: 'running' },
    { name: 'Architecture', order: 4, status: 'awaiting_review' }, { name: 'Build', order: 5, status: 'rejected' }, { name: 'Deploy', order: 6, status: 'not_started' },
  ]
  it('the later phases named are those after this one that have started, in order', () => {
    expect(laterStartedNames(phases, { order: 2 })).toEqual(['Design', 'Architecture', 'Build'])
    expect(laterStartedNames(phases, { order: 5 })).toEqual([])
  })
  it('earlier phases and the phase itself are never named', () => {
    expect(laterStartedNames(phases, { order: 3 })).not.toContain('Design'); expect(laterStartedNames(phases, { order: 3 })).not.toContain('Requirements')
  })
  it('the server wrote one request for Reopen: POST .../phases/<key>/reopen with the reason and the name, nothing else', async () => {
    const seen: { url: string; method?: string; body?: unknown; actor?: string }[] = []
    const client = makeClient(async (url, init) => {
      seen.push({ url: String(url), method: init?.method, body: JSON.parse(String(init?.body)), actor: (init?.headers as Record<string, string>)['X-Actor'] })
      return new Response(JSON.stringify(gateReopen), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    await client.reopenPhase('p1', 'design', 'Ann', 'the brief changed')
    expect(seen).toEqual([{ url: '/api/projects/p1/phases/design/reopen', method: 'POST', body: { reason: 'the brief changed' }, actor: 'Ann' }])
  })
  it('pressing a button: Reopen and Request changes open their forms; a sent-back phase with notes re-runs only those; the rest act at once', () => {
    expect(pressRoute('reopen', { status: 'approved' }, 0)).toBe('open_reopen')
    expect(pressRoute('request_changes', { status: 'awaiting_review' }, 0)).toBe('open_send_back')
    expect(pressRoute('run', { status: 'rejected' }, 2)).toBe('rerun_notes')
    expect(pressRoute('run', { status: 'rejected' }, 0)).toBe('act')
    expect(pressRoute('run', { status: 'running' }, 2)).toBe('act')
    expect(pressRoute('approve', { status: 'awaiting_review' }, 2)).toBe('act')
    expect(pressRoute('finish', { status: 'running' }, 0)).toBe('act')
  })
})


describe('Copy the suggested fix', () => {
  it('every finding that has a fix carries a Copy button named for its target', () => {
    const out = html(<ReviewPanel review={review} shownVersion={review.version_reviewed} />)
    for (const f of review.findings.filter((x) => x.fix)) expect(out).toContain(`aria-label="Copy the suggested fix for ${f.target}"`)
    expect(out.split('>Copy<').length - 1).toBe(review.findings.filter((x) => x.fix).length)
  })
  it('the fix says where to paste it', () => {
    expect(html(<FindingRow finding={{ severity: 'high', target: 'PER-001', problem: 'p', fix: 'Rewrite it.' }} />)).toContain('paste it into Edit by hand')
  })
  it('a long fix of several lines is copied and shown whole', () => {
    const fix = 'PER-001 Customer. Goal: see their own usage [SET-CHR-001].\nSuccess: they find it fast. Derives from: [SET-CHR-001]'
    const out = html(<FindingRow finding={{ severity: 'high', target: 'PER-001', problem: 'p', fix }} />)
    expect(out).toContain('Success: they find it fast.')
  })
  it('a finding with no fix has no Copy button', () => {
    const out = html(<FindingRow finding={{ severity: 'low', target: 'General', problem: 'thin', fix: '' }} />)
    expect(out).not.toContain('Copy'); expect(out).not.toContain('Suggested fix')
  })
  it('the fix text is still shown beside the button', () => {
    expect(html(<FindingRow finding={{ severity: 'high', target: 'PER-001', problem: 'p', fix: 'Rewrite PER-001 as a customer.' }} />)).toContain('Rewrite PER-001 as a customer.')
  })
  it('the button starts as Copy, and its three words are the ones a person reads', () => {
    expect(html(<CopyButton text="x" what="the fix" />)).toContain('>Copy<')
    expect(COPY_LABEL).toEqual({ idle: 'Copy', done: 'Copied', failed: 'Could not copy' })
  })
  it('text with markup in it is still inert', () => {
    const out = html(<FindingRow finding={{ severity: 'low', target: '<b>x</b>', problem: 'p', fix: '<script>alert(1)</script>' }} />)
    expect(out).not.toContain('<script>'); expect(out).not.toContain('<b>x</b>')
  })
})
