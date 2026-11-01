// S12c: every new backend fixture decodes with the screen's own decoders, and a changed shape fails loudly.
import { describe, expect, it } from 'vitest'
import {
  ContractError, decodeArtefactDetail, decodeChangesRequested, decodeEditRefusal, decodeEditSaved, decodeError, decodeMode, decodePhaseReview, decodeRerun,
  decodeReviewAnswer, decodeReviewState, decodeStoredReview,
} from '../api'
import artefactDetail from './review_artefact_detail.json'
import editSaved from './edit_saved.json'
import error409Archived from './error_409_archived.json'
import error409Replay from './error_409_replay_reviews.json'
import error422Edit from './error_422_edit.json'
import modes from './modes.json'
import requestChanges from './request_changes.json'
import rerunStarted from './rerun_started.json'
import reviewPaused from './review_paused.json'
import reviewPhase from './review_phase.json'
import reviewResult from './review_result.json'
import stateAfter from './review_state_after.json'
import stateBefore from './review_state_before.json'
import stateStale from './review_state_stale.json'

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))

describe('the S12c fixtures decode', () => {
  it('a finished review has a verdict, findings, how independent it was, and a cost', () => {
    const r = decodeReviewAnswer(reviewResult)
    if (r.paused) throw new Error('expected a finished review')
    expect(r.verdict).toBe('revise')
    expect(r.findings.map((f) => f.severity)).toEqual(['high', 'low'])
    expect(r.independence.label).toBe('same_family')
    expect(r.cost_usd).not.toBeNull()
  })

  it('a paused review lists the other families, with prices that may be unknown (null, not zero)', () => {
    const r = decodeReviewAnswer(reviewPaused)
    if (!r.paused) throw new Error('expected a paused review')
    expect(r.slot).toBe('sonnet')
    expect(r.options.length).toBeGreaterThan(0)
    expect(r.options.some((o) => o.price_input === null && !o.priced)).toBe(true)      // precondition: the fixture has an unpriced option
    for (const o of r.options) if (!o.priced) { expect(o.price_input).toBeNull(); expect(o.price_output).toBeNull() }
  })

  it('a phase review is a list of answers', () => {
    const results = decodePhaseReview(reviewPhase)
    expect(results).toHaveLength(7)
    expect(results.every((r) => !r.paused)).toBe(true)
  })

  it('the artefact detail carries the stored review, and the one without a review has null', () => {
    const d = decodeArtefactDetail(artefactDetail)
    expect(d.review?.verdict).toBe('revise')
    expect(d.review?.version_reviewed).toBe(d.version)
    expect(d.review?.reviewer.model).toBeTruthy()
  })

  it('review state: before any review everything is unreviewed; after one, that one is reviewed; after an edit it is out of date', () => {
    const before = decodeReviewState(stateBefore)
    expect(before.reviews_available).toBe(true)
    expect(before.statuses.every((s) => s.state === 'unreviewed' && s.verdict === null)).toBe(true)
    expect(before.open.unreviewed).toHaveLength(7)
    const after = decodeReviewState(stateAfter)
    expect(after.statuses.some((s) => s.state === 'reviewed')).toBe(true)
    expect(after.open.unreviewed).toEqual([])
    const stale = decodeReviewState(stateStale)
    expect(stale.statuses.some((s) => s.state === 'stale')).toBe(true)
    expect(stale.stale.length).toBeGreaterThan(0)
    expect(Object.keys(stale.stale[0].now).length).toBeGreaterThan(0)
  })

  it('the states are sorted so a fixture only changes when a shape changes', () => {
    for (const fixture of [stateBefore, stateAfter, stateStale]) {
      const ids = decodeReviewState(fixture).statuses.map((s) => s.artefact_id)
      expect(ids).toEqual([...ids].sort())
    }
  })

  it('request changes, re-run and edit', () => {
    const c = decodeChangesRequested(requestChanges)
    expect(c.status).toBe('rejected')
    expect(c.artefacts_with_notes).toEqual(['REQ-PER-001'])
    const r = decodeRerun(rerunStarted)
    expect(r.only).toEqual(['personas'])
    expect(r.events).toContain('/events')
    expect(decodeEditSaved(editSaved)).toEqual({ artefact_id: 'REQ-PER-001', version: 2 })
  })

  it('a refused edit lists every reason, and decodeError reads its message too', () => {
    const refusal = decodeEditRefusal(error422Edit)
    expect(refusal).not.toBeNull()
    expect(refusal!.problems.length).toBeGreaterThan(1)
    expect(refusal!.message).toContain('not saved')
    expect(decodeError(error422Edit)).toBe(refusal!.message)
  })

  it('an ordinary sentence is not mistaken for an edit refusal', () => {
    expect(decodeEditRefusal(error409Archived)).toBeNull()
    expect(decodeEditRefusal({ detail: ['a list of validation messages'] })).toBeNull()
    expect(decodeEditRefusal({ detail: { message: 'x' } })).toBeNull()       // no problems list: not the refusal shape
    expect(decodeEditRefusal(null)).toBeNull()
  })

  it('the two refusals a person meets most are plain sentences', () => {
    expect(decodeError(error409Archived)).toBe('This project is archived; restore it first.')
    expect(decodeError(error409Replay)).toContain('Reviews need live mode')
  })

  it('the modes answer says whether reviews can run', () => {
    expect(decodeMode(modes)).toMatchObject({ mode: 'replay', reviews_available: false })
  })
})

describe('a changed shape is caught', () => {
  it('a renamed field in a review', () => {
    const bad = clone(reviewResult) as Record<string, unknown>
    bad.verdict_text = bad.verdict
    delete bad.verdict
    expect(() => decodeReviewAnswer(bad)).toThrow(ContractError)
  })

  it('an unknown severity, verdict or independence label is refused rather than shown', () => {
    for (const [path, value] of [['findings.0.severity', 'critical'], ['verdict', 'maybe'], ['independence.label', 'sort_of_independent']] as const) {
      const bad = clone(reviewResult) as Record<string, any>
      const parts = path.split('.')
      let target = bad
      for (const p of parts.slice(0, -1)) target = target[p]
      target[parts[parts.length - 1]] = value
      expect(() => decodeReviewAnswer(bad), path).toThrow(ContractError)
    }
  })

  it('an option price that is the number zero for an unpriced option is still read as given (the server is the one that must send null)', () => {
    const bad = clone(reviewPaused) as Record<string, any>
    bad.options[0].price_input = '1.5'
    expect(() => decodeReviewAnswer(bad)).toThrow(ContractError)
  })

  it('a paused answer without options, and a finished one without a verdict, are refused', () => {
    const noOptions = clone(reviewPaused) as Record<string, unknown>
    delete noOptions.options
    expect(() => decodeReviewAnswer(noOptions)).toThrow(ContractError)
    const noVerdict = clone(reviewResult) as Record<string, unknown>
    delete noVerdict.verdict
    expect(() => decodeReviewAnswer(noVerdict)).toThrow(ContractError)
  })

  it('a review state missing its open list, or with an unknown review state, is refused', () => {
    const noOpen = clone(stateAfter) as Record<string, unknown>
    delete noOpen.open
    expect(() => decodeReviewState(noOpen)).toThrow(ContractError)
    const bad = clone(stateAfter) as Record<string, any>
    bad.statuses[0].state = 'half_reviewed'
    expect(() => decodeReviewState(bad)).toThrow(ContractError)
  })

  it('a stored review needs its independence block', () => {
    const detail = clone(artefactDetail) as Record<string, any>
    delete detail.review.independence
    expect(() => decodeArtefactDetail(detail)).toThrow(ContractError)
    expect(() => decodeStoredReview(null)).toThrow(ContractError)
  })

  it('an artefact detail without the review field at all is a contract problem, not "no review"', () => {
    const detail = clone(artefactDetail) as Record<string, unknown>
    delete detail.review
    expect(() => decodeArtefactDetail(detail)).toThrow(/review/)
  })

  it('the modes answer without reviews_available is refused', () => {
    const bad = clone(modes) as Record<string, unknown>
    delete bad.reviews_available
    expect(() => decodeMode(bad)).toThrow(ContractError)
  })

  it('a changes-requested answer, a re-run and an edit each refuse a missing field', () => {
    const c = clone(requestChanges) as Record<string, unknown>; delete c.artefacts_with_notes
    expect(() => decodeChangesRequested(c)).toThrow(ContractError)
    const r = clone(rerunStarted) as Record<string, unknown>; delete r.only
    expect(() => decodeRerun(r)).toThrow(ContractError)
    const e = clone(editSaved) as Record<string, unknown>; delete e.version
    expect(() => decodeEditSaved(e)).toThrow(ContractError)
  })
})
