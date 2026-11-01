import { describe, expect, it } from 'vitest'
import { decodeEvent, type RunEvent } from '../api'
import eventExamples from '../contract/events.json'
import { applyAll, applyEvent, capUsed, counts, idle, isLive, type Progress } from './runProgress'

const RUN = 'run1'
let nextId = 0
const base = () => ({ id: ++nextId, run_id: RUN, at: '2026-01-01T00:00:00.000Z' })
const totals = (over: Partial<RunEvent & { cost_usd: number | null }> = {}) => ({
  artefacts: { done: 2, failed: 0, skipped: 0, not_started: 0 }, calls: 2, cost_usd: 0.05, cost_is_partial: false, tokens_in: 1, tokens_out: 1, elapsed_seconds: 3, over_budget_by_usd: null, ...over,
})
const started = (keys: string[], over: Record<string, unknown> = {}): RunEvent => ({ ...base(), type: 'run.started', phase: 'requirements', artefacts: keys, concurrency: 3, review: false, max_cost_usd: 2, max_seconds: 1800, ...over }) as RunEvent
const begun = (key: string): RunEvent => ({ ...base(), type: 'artefact.started', key })
const finished = (key: string, cost: number | null = 0.01, over: Record<string, unknown> = {}): RunEvent =>
  ({ ...base(), type: 'artefact.finished', key, artefact_id: `ID-${key}`, version: 1, attempts: 1, cost_usd: cost, items: 3, flags: 0, author: 'agent:x@m', ...over }) as RunEvent
const failed = (key: string, reason = 'it failed'): RunEvent => ({ ...base(), type: 'artefact.failed', key, reason })
const skipped = (key: string, reason = 'blocked by a'): RunEvent => ({ ...base(), type: 'artefact.skipped', key, reason })
const ended = (type: 'run.finished' | 'run.stopped', status: string, reason: string | null, extra = {}): RunEvent => ({ ...base(), type, status, reason, totals: totals(extra) }) as RunEvent
const row = (p: Progress, key: string) => p.rows.find((r) => r.key === key)!

describe('the run panel\'s state follows the events', () => {
  it('starts idle with nothing to show', () => {
    expect(idle.status).toBe('idle')
    expect(idle.rows).toEqual([])
    expect(isLive(idle)).toBe(false)
  })

  it('a started run lists every artefact as waiting, with the caps it was given', () => {
    const p = applyEvent(idle, started(['a', 'b', 'c']))
    expect(p.status).toBe('running')
    expect(isLive(p)).toBe(true)
    expect(p.rows.map((r) => [r.key, r.state])).toEqual([['a', 'waiting'], ['b', 'waiting'], ['c', 'waiting']])
    expect([p.concurrency, p.capUsd, p.capSeconds]).toEqual([3, 2, 1800])
  })

  it('writing, then done, with the artefact id, version, items and cost', () => {
    let p = applyAll([started(['a']), begun('a')])
    expect(row(p, 'a').state).toBe('writing')
    p = applyEvent(p, finished('a', 0.0123))
    expect(row(p, 'a')).toMatchObject({ state: 'done', artefactId: 'ID-a', version: 1, items: 3, costUsd: 0.0123, attempts: 1 })
  })

  it('an attempt that will be repaired shows as retrying, and a clean one stays writing', () => {
    // Ids are given when an event is made, so make them in the order they happen.
    const first = [started(['a']), begun('a')]
    const retry: RunEvent = { ...base(), type: 'artefact.attempt', key: 'a', attempt: 1, will_repair: true, problems: 2, fell_back: false }
    let p = applyAll([...first, retry])
    expect(row(p, 'a')).toMatchObject({ state: 'retrying', attempts: 2 })
    p = applyEvent(p, finished('a', 0.01, { attempts: 2 }))
    expect(row(p, 'a')).toMatchObject({ state: 'done', attempts: 2 })
    const second = [started(['b']), begun('b')]
    const fell: RunEvent = { ...base(), type: 'artefact.attempt', key: 'b', attempt: 1, will_repair: false, problems: 0, fell_back: true }
    expect(row(applyAll([...second, fell]), 'b').state).toBe('writing')
  })

  it('failed and skipped show the server\'s reason, as given', () => {
    const p = applyAll([started(['a', 'b']), begun('a'), failed('a', 'the model said no <b>'), skipped('b', 'blocked by a')])
    expect(row(p, 'a')).toMatchObject({ state: 'failed', reason: 'the model said no <b>' })
    expect(row(p, 'b')).toMatchObject({ state: 'skipped', reason: 'blocked by a' })
    expect(counts(p)).toEqual({ waiting: 0, writing: 0, retrying: 0, done: 0, failed: 1, skipped: 1 })
  })

  it('the cost so far is the sum of finished artefacts, and becomes unknown the moment one has no price', () => {
    let p = applyAll([started(['a', 'b']), finished('a', 0.01), finished('b', 0.02)])
    expect(p.costUsd).toBeCloseTo(0.03)
    expect(p.costKnown).toBe(true)
    p = applyAll([started(['a', 'b']), finished('a', 0.01), finished('b', null)])
    expect(p.costUsd).toBeNull()
    expect(p.costKnown).toBe(false)
  })

  it('the cap used is a share of the cap, held at 1, and absent when there is no cap or no known cost', () => {
    expect(capUsed(applyAll([started(['a']), finished('a', 0.5)]))).toBeCloseTo(0.25)
    expect(capUsed(applyAll([started(['a']), finished('a', 9)]))).toBe(1)
    expect(capUsed(applyAll([started(['a'], { max_cost_usd: null }), finished('a', 0.5)]))).toBeNull()
    expect(capUsed(applyAll([started(['a']), finished('a', null)]))).toBeNull()
  })

  it('a finished run takes the server\'s totals as the truth', () => {
    const p = applyAll([started(['a', 'b']), finished('a', 0.01), finished('b', 0.01), ended('run.finished', 'finished', null, { cost_usd: 0.0199 })])
    expect(p.status).toBe('finished')
    expect(isLive(p)).toBe(false)
    expect(p.costUsd).toBe(0.0199)
    expect(p.totals?.calls).toBe(2)
  })

  it('a stopped run keeps its reason, and artefacts that never started say so', () => {
    const p = applyAll([started(['a', 'b']), finished('a'), ended('run.stopped', 'stopped', 'budget')])
    expect(p.status).toBe('stopped')
    expect(p.stopReason).toBe('budget')
    expect(row(p, 'b').reason).toContain('budget')
    expect(row(p, 'b').state).toBe('waiting')
  })

  it('partial costs in the server\'s totals make the cost unknown', () => {
    const p = applyAll([started(['a']), finished('a'), ended('run.finished', 'finished', null, { cost_is_partial: true })])
    expect(p.costKnown).toBe(false)
  })

  it('reviews attach to the row of their artefact', () => {
    const earlier = [started(['a']), finished('a')]
    const r1: RunEvent = { ...base(), type: 'review.started', artefact_id: 'ID-a' }
    let p = applyAll([...earlier, r1])
    expect(row(p, 'a').review).toBe('running')
    const r2: RunEvent = { ...base(), type: 'review.finished', artefact_id: 'ID-a', verdict: 'ok', label: 'independent' }
    p = applyEvent(p, r2)
    expect(row(p, 'a')).toMatchObject({ review: 'done', reviewNote: 'ok (independent)' })
    const paused: RunEvent = { ...base(), type: 'review.paused', artefact_id: 'ID-a', reason: 'the reviewer is unavailable', slot: null, options: [] }
    expect(row(applyEvent(p, paused), 'a')).toMatchObject({ review: 'paused', reviewNote: 'the reviewer is unavailable' })
  })

  it('a review paused because the reviewer is unavailable says to choose another family, naming the slot', () => {
    const before = applyAll([started(['a']), finished('a')])
    const choice: RunEvent = { ...base(), type: 'review.paused', artefact_id: 'ID-a', reason: null, slot: 'sonnet', options: ['openai', 'gemini'] }
    const note = row(applyEvent(before, choice), 'a').reviewNote
    expect(note).toContain('sonnet')
    expect(note).toContain('choose another family')
    const noOptions: RunEvent = { ...base(), type: 'review.paused', artefact_id: 'ID-a', reason: null, slot: 'sonnet', options: [] }
    expect(row(applyEvent(before, noOptions), 'a').reviewNote).toBe('the reviewer is not available')
  })

  describe('the attempt number shown beside an artefact', () => {
    const attempt = (key: string, n: number, willRepair: boolean): RunEvent => ({ ...base(), type: 'artefact.attempt', key, attempt: n, will_repair: willRepair, problems: willRepair ? 1 : 0, fell_back: false }) as RunEvent
    const failedFor = (key: string): RunEvent => ({ ...base(), type: 'artefact.failed', key, reason: 'the reply failed its checks after 3 attempt(s) (1 problem(s))' }) as RunEvent

    it('while a repair is coming it shows the attempt now being written', () => {
      nextId = 0
      const p = applyAll([started(['a']), begun('a'), attempt('a', 1, true)])
      expect(row(p, 'a')).toMatchObject({ state: 'retrying', attempts: 2, made: 1 })
    })
    it("a failure after the last allowed attempt shows 3, not the 4 that would have come next (the user's own failing run)", () => {
      nextId = 0
      const p = applyAll([started(['a']), begun('a'), attempt('a', 1, true), attempt('a', 2, true), attempt('a', 3, true), failedFor('a')])
      expect(row(p, 'a')).toMatchObject({ state: 'failed', attempts: 3, made: 3 })
    })
    it('the same failure seen live, one event at a time, shows 2 then 3 then 4 only while retrying, and 3 once it has failed', () => {
      nextId = 0
      let p = applyAll([started(['a']), begun('a')])
      const shown: number[] = []
      for (const e of [attempt('a', 1, true), attempt('a', 2, true), attempt('a', 3, true), failedFor('a')]) { p = applyEvent(p, e); shown.push(row(p, 'a').attempts) }
      expect(shown).toEqual([2, 3, 4, 3])
    })
    it('a failure after a single refused attempt shows 1', () => {
      nextId = 0
      expect(row(applyAll([started(['a']), begun('a'), attempt('a', 1, true), failedFor('a')]), 'a')).toMatchObject({ state: 'failed', attempts: 1 })
    })
    it('a failure before any model call (no skill, a refusal) shows the count it had, never zero attempts invented', () => {
      nextId = 0
      expect(row(applyAll([started(['a']), begun('a'), failedFor('a')]), 'a')).toMatchObject({ state: 'failed', attempts: 1, made: 0 })
    })
    it('a success after a repair shows the attempts the server counted', () => {
      nextId = 0
      expect(row(applyAll([started(['a']), begun('a'), attempt('a', 1, true), finished('a', 0.01, { attempts: 2 })]), 'a')).toMatchObject({ state: 'done', attempts: 2 })
    })
    it('a replayed event cannot lower what was made', () => {
      nextId = 0
      const events = [started(['a']), begun('a'), attempt('a', 1, true), attempt('a', 2, true)]
      const p = applyAll(events)
      expect(applyEvent(p, events[2])).toBe(p)
      expect(row(p, 'a').made).toBe(2)
    })
  })

  it('a run that ended without totals (it crashed, or the backend restarted) keeps what finished and says why', () => {
    nextId = 0
    const earlier = [started(['a', 'b']), finished('a', 0.02)]      // ids are given when an event is made, so make them in the order they happen
    const stopped: RunEvent = { ...base(), type: 'run.stopped', status: 'interrupted', reason: 'the backend stopped while this run was in progress', totals: null }
    const p = applyAll([...earlier, stopped])
    expect(p.status).toBe('interrupted')
    expect(p.totals).toBeNull()
    expect(p.failureNote).toBe('the backend stopped while this run was in progress')
    expect(p.costUsd).toBeCloseTo(0.02)                   // the tally from the artefacts that did finish is kept
    expect(row(p, 'b').state).toBe('waiting')
    expect(row(p, 'b').reason).toContain('not started')
    expect(isLive(p)).toBe(false)
  })

  it('a new run clears the note of the last one', () => {
    nextId = 0
    const first = started(['a'])
    const stopped: RunEvent = { ...base(), type: 'run.stopped', status: 'failed', reason: 'it broke', totals: null }
    const next = { ...started(['z']), run_id: 'run2' } as RunEvent
    const p = applyAll([first, stopped, next])
    expect(applyAll([first, stopped]).failureNote).toBe('it broke')      // precondition: the note was there before the new run
    expect(p.failureNote).toBeNull()
  })

  it('an event for an artefact the run did not announce still gets a row', () => {
    expect(applyAll([started(['a']), begun('zzz')]).rows.map((r) => r.key)).toEqual(['a', 'zzz'])
  })
})

describe('idempotence and order', () => {
  const sequence = () => { nextId = 0; return [started(['a', 'b']), begun('a'), begun('b'), finished('a'), failed('b'), ended('run.finished', 'failed', null)] }

  it('applying the same event twice changes nothing', () => {
    const events = sequence()
    const once = applyAll(events)
    expect(applyAll([...events, ...events])).toEqual(once)
    expect(applyEvent(once, events[3])).toBe(once)
  })

  it('an older event arriving late is ignored', () => {
    const events = sequence()
    const done = applyAll(events)
    expect(applyEvent(done, events[1])).toBe(done)
  })

  it('a panel rebuilt from the stored log equals one that watched live', () => {
    const events = sequence()
    let live: Progress = idle
    for (const e of events) live = applyEvent(live, e)
    expect(applyAll(events)).toEqual(live)
    // ...and one that reconnected halfway and replayed from the beginning
    const half = applyAll(events.slice(0, 3))
    expect(applyAll(events, half)).toEqual(live)
  })

  it('events of another run do not leak into this panel, but their ids are still passed', () => {
    const events = sequence()
    const mine = applyAll(events.slice(0, 2))
    const other = { ...begun('a'), run_id: 'other', id: 99 } as RunEvent
    const after = applyEvent(mine, other)
    expect(after.rows).toEqual(mine.rows)
    expect(after.runId).toBe(mine.runId)
    expect(after.lastEventId).toBe(99)      // so a reconnect does not ask for it again
  })

  it('a new run replaces the one shown, so opening the stream from the start ends on the latest run', () => {
    nextId = 0
    const run1 = [started(['a', 'b']), finished('a'), finished('b'), ended('run.finished', 'finished', null)]
    const next = (e: RunEvent): RunEvent => ({ ...e, run_id: 'run2', id: ++nextId }) as RunEvent
    const run2 = [next(started(['c'])), next(begun('c'))]
    const p = applyAll([...run1, ...run2])
    expect(p.runId).toBe('run2')
    expect(p.rows.map((r) => [r.key, r.state])).toEqual([['c', 'writing']])
    expect(p.status).toBe('running')
    expect(p.totals).toBeNull()
    expect(p.costUsd).toBe(0)
  })

  it('the late events of an old run, after a new one started, are ignored', () => {
    nextId = 0
    const old = [started(['a']), begun('a')]
    const fresh = { ...started(['z']), run_id: 'run2' } as RunEvent
    const late = { ...finished('a'), id: ++nextId + 5 } as RunEvent
    const p = applyAll([...old, fresh, late])
    expect(p.runId).toBe('run2')
    expect(p.rows.map((r) => r.key)).toEqual(['z'])
  })

  it('the last event id moves forward with every applied event', () => {
    const events = sequence()
    expect(applyAll(events).lastEventId).toBe(events[events.length - 1].id)
  })

  it('does not change the state it was given', () => {
    const events = sequence()
    const before = applyAll(events.slice(0, 2))
    const snapshot = JSON.stringify(before)
    applyAll(events.slice(2), before)
    expect(JSON.stringify(before)).toBe(snapshot)
  })
})

describe('with the backend\'s own example of each event', () => {
  it('every real example applies without throwing, in a plausible order', () => {
    const order = ['run.started', 'artefact.started', 'artefact.attempt', 'artefact.finished', 'artefact.failed', 'artefact.skipped', 'review.started', 'review.finished', 'review.paused', 'run.finished']
    const examples = eventExamples as Record<string, Record<string, unknown>>
    const decoded = order.map((t, i) => decodeEvent(i + 1, t, { ...examples[t], run_id: 'r' }))
    expect(() => applyAll(decoded)).not.toThrow()
    const p = applyAll(decoded)
    expect(p.status).toBe('finished')
    expect(p.rows.length).toBeGreaterThan(0)
  })
})
