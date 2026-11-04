// S12b: every new backend fixture must decode with the screen's own decoders, and a renamed or retyped field must fail loudly.
import { describe, expect, it } from 'vitest'
import {
  ContractError, EVENT_TYPES, decodeArtefactDetail, decodeArtefactList, decodeDocuments, decodeError, decodeEvent, decodeGate, decodeRun, decodeRunStarted,
  decodeRuns, decodeSample, decodeSearch, decodeUpload,
} from '../api'
import artefactDetail from './artefact_detail.json'
import artefacts from './artefacts.json'
import documentAdded from './document_added.json'
import documents from './documents.json'
import error409 from './error_409.json'
import events from './events.json'
import gateApprove from './gate_approve.json'
import gateFinish from './gate_finish.json'
import runDetail from './run_detail.json'
import runStarted from './run_started.json'
import runs from './runs.json'
import sample from './sample.json'
import search from './search.json'

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))

// An event type with more than one shape has one fixture per shape, named `type` for the first and `type.shape` for the others.
const typeOf = (fixtureName: string) => EVENT_TYPES.find((t) => fixtureName === t || fixtureName.startsWith(t + '.'))!

describe('the S12b fixtures decode', () => {
  it('the sample', () => {
    const s = decodeSample(sample)
    expect(s.name).toBe('Meeting Room Booking')
    expect(s.document.filename).toBe('meeting-room-policy.md')
    expect(s.document.text.length).toBeGreaterThan(50)
  })

  it('an upload: the document, and flags with a place but never the matched text', () => {
    const u = decodeUpload(documentAdded)
    expect(u.source_id).toBe('DOC-001')
    expect(u.flags.length).toBeGreaterThan(0)    // precondition: the fixture really has a flag
    expect(Object.keys(u.flags[0]).sort()).toEqual(['heading', 'klass', 'length', 'line', 'rule'])
    expect(JSON.stringify(u)).not.toContain('jane.doe')
  })

  it('the document list has no flags field (flags belong to the upload result only)', () => {
    const list = decodeDocuments(documents)
    expect(list).toHaveLength(1)
    expect('flags' in list[0]).toBe(false)
  })

  it('search hits', () => {
    const r = decodeSearch(search)
    expect(r.hits.length).toBeGreaterThan(0)
    expect(r.hits[0].source_id).toMatch(/^DOC-\d+#\d+$/)
  })

  it('the artefact list and one artefact in full', () => {
    const list = decodeArtefactList(artefacts)
    expect(list.map((a) => a.type)).toEqual([...list.map((a) => a.type)].sort())
    const d = decodeArtefactDetail(artefactDetail)
    expect(d.type).toBe('functional_requirements')
    expect(d.generation?.items).toEqual(['FR-001', 'FR-002'])
    expect(d.sources.some((s) => s.available)).toBe(true)
    expect(d.sources.some((s) => !s.available && s.text === null)).toBe(true)      // an unavailable source carries no text
    expect(d.links.derived_from.length).toBeGreaterThan(0)
    expect(d.links.used_by.length).toBeGreaterThan(0)
    expect(d.versions[0].number).toBe(1)
  })

  it('runs and a single run', () => {
    const list = decodeRuns(runs)
    expect(list[0].phase).toBe('requirements')
    const one = decodeRun(runDetail)
    expect(one.status).toBe('finished')
    expect(one.totals?.artefacts.done).toBe(7)
  })

  it('a stored run may carry why each artefact failed, and an older one without it still decodes', () => {
    expect(decodeRun(runDetail).totals?.failures).toEqual({})
    const failed = { ...(runDetail as Record<string, unknown>), totals: { ...((runDetail as Record<string, unknown>).totals as Record<string, unknown>),
      failures: { frontend_code: { reason: 'could not be produced', problems: ['one', 'two'], cut_off: true } } } }
    expect(decodeRun(failed).totals?.failures).toEqual({ frontend_code: { reason: 'could not be produced', problems: ['one', 'two'], cut_off: true } })
  })
  it('a malformed failure record is refused, naming the field', () => {
    const base = runDetail as Record<string, unknown>
    const bad = (failures: unknown) => ({ ...base, totals: { ...(base.totals as Record<string, unknown>), failures } })
    expect(() => decodeRun(bad({ x: { reason: 1, problems: [], cut_off: false } }))).toThrow(/reason/)
    expect(() => decodeRun(bad({ x: { reason: 'r', problems: 'no', cut_off: false } }))).toThrow(/problems/)
    expect(() => decodeRun(bad({ x: { reason: 'r', problems: [], cut_off: 'yes' } }))).toThrow(/cut_off/)
    expect(() => decodeRun(bad('nope'))).toThrow(ContractError)
  })

  it('a started run, the two gate answers, and a 409 sentence', () => {
    expect(decodeRunStarted(runStarted).events).toContain('/events')
    expect(decodeGate(gateFinish)).toMatchObject({ status: 'awaiting_review', decision: null })
    expect(decodeGate(gateApprove)).toMatchObject({ status: 'approved', decision: 'approve' })
    expect(decodeError(error409)).toContain('cannot go from')
  })

  it('there is a real example of every event type, and each decodes to its own type', () => {
    const examples = events as Record<string, unknown>
    expect([...new Set(Object.keys(examples).map(typeOf))].sort()).toEqual([...EVENT_TYPES].sort())
    let id = 1
    for (const name of Object.keys(examples)) {
      const decoded = decodeEvent(id++, typeOf(name), examples[name])
      expect(decoded.type).toBe(typeOf(name))
    }
  })

  it('review.paused: the reviewer-unavailable shape carries the slot and the other families; the other carries a reason', () => {
    const examples = events as Record<string, unknown>
    const choice = decodeEvent(1, 'review.paused', examples['review.paused'])
    const failure = decodeEvent(2, 'review.paused', examples['review.paused.reason'])
    if (choice.type !== 'review.paused' || failure.type !== 'review.paused') throw new Error('wrong type')
    expect(choice.slot).toBe('sonnet')
    expect(choice.options.length).toBeGreaterThan(0)
    expect(choice.reason).toBeNull()
    expect(failure.reason).toContain('failed its checks')
    expect(failure.options).toEqual([])
    expect(failure.slot).toBeNull()
  })

  it('run.stopped: a run stopped early has totals; one that crashed or was interrupted has none, and says why', () => {
    const examples = events as Record<string, unknown>
    const early = decodeEvent(1, 'run.stopped', examples['run.stopped'])
    const short = decodeEvent(2, 'run.stopped', examples['run.stopped.short'])
    if (early.type !== 'run.stopped' || short.type !== 'run.stopped') throw new Error('wrong type')
    expect(early.totals).not.toBeNull()
    expect(short.totals).toBeNull()
    expect(short.status).toBe('interrupted')
    expect(short.reason).toContain('backend stopped')
  })

  it('a review.paused with neither a reason nor a reviewer slot is a contract problem, not silence', () => {
    expect(() => decodeEvent(1, 'review.paused', { run_id: 'r', at: 't', artefact_id: 'A' })).toThrow(ContractError)
  })

  it('a review.paused whose options are not a list of text is refused', () => {
    expect(() => decodeEvent(1, 'review.paused', { run_id: 'r', at: 't', artefact_id: 'A', slot: 's', options: [1, 2] })).toThrow(ContractError)
  })
})

describe('a changed shape is caught', () => {
  it('a renamed field in an artefact is a ContractError', () => {
    const bad = clone(artefactDetail) as Record<string, unknown>
    bad.body_text = bad.body
    delete bad.body
    expect(() => decodeArtefactDetail(bad)).toThrow(ContractError)
  })

  it('a retyped cost is a ContractError, and a null cost is allowed (unknown is not zero)', () => {
    const bad = clone(artefactDetail) as Record<string, unknown>
    bad.cost_usd = '0.01'
    expect(() => decodeArtefactDetail(bad)).toThrow(ContractError)
    const unknown = clone(artefactDetail) as Record<string, unknown>
    unknown.cost_usd = null
    expect(decodeArtefactDetail(unknown).cost_usd).toBeNull()
  })

  it('an unknown run status and an unknown event type are refused', () => {
    const bad = clone(runDetail) as Record<string, unknown>
    bad.status = 'exploded'
    expect(() => decodeRun(bad)).toThrow(ContractError)
    expect(() => decodeEvent(1, 'artefact.exploded', {})).toThrow(ContractError)
  })

  it('an event missing a field names the field', () => {
    const e = clone((events as Record<string, unknown>)['artefact.finished']) as Record<string, unknown>
    delete e.artefact_id
    expect(() => decodeEvent(1, 'artefact.finished', e)).toThrow(/artefact_id/)
  })

  it('every event decoder refuses a missing run_id', () => {
    for (const type of Object.keys(events as Record<string, unknown>)) {
      const e = clone((events as Record<string, unknown>)[type]) as Record<string, unknown>
      delete e.run_id
      expect(() => decodeEvent(1, typeOf(type), e), type).toThrow(ContractError)
    }
  })

  it('an upload without its flags list is refused rather than treated as clean', () => {
    const bad = clone(documentAdded) as Record<string, unknown>
    delete bad.flags
    expect(() => decodeUpload(bad)).toThrow(ContractError)
  })
})
