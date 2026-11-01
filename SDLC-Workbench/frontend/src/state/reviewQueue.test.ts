import { describe, expect, it } from 'vitest'
import { BackendUnreachable, ServerRefused, type ReviewAnswer } from '../api'
import {
  costSoFar, finishRun, headline, markDone, markReviewing, requestStop, runReviewQueue, startRun, stopsTheQueue, tally, type QueueDeps, type ReviewRun,
} from './reviewQueue'

const done = (id: string, over: Partial<Extract<ReviewAnswer, { paused: false }>> = {}): ReviewAnswer => ({
  paused: false, artefact_id: id, version: 1, verdict: 'ok', summary: 's', findings: [], independence: { label: 'independent', author_family: 'a', reviewer_family: 'b', fell_back: false },
  cost_usd: 0.01, attempts: 1, ...over,
})
const pausedAnswer = (id: string, slot = 'sonnet'): ReviewAnswer => ({ paused: true, artefact_id: id, slot, options: [] })
const queue = ['A', 'B', 'C'].map((id) => ({ id, name: `Artefact ${id}` }))

/** A fake reviewer that records what it was asked and when, and answers from a script. */
function fake(script: Record<string, ReviewAnswer | Error | (() => ReviewAnswer | Error)>, extra: Partial<QueueDeps> = {}) {
  const calls: { id: string; choice: { slot?: string; exclude?: string[] } }[] = []
  const snapshots: ReviewRun[] = []
  const deps: QueueDeps = {
    async review(id, choice) {
      calls.push({ id, choice })
      const r = script[id]
      const answer = typeof r === 'function' ? r() : r
      if (answer instanceof Error) throw answer
      return answer ?? done(id)
    },
    shouldStop: () => false,
    onUpdate: (run) => snapshots.push(run),
    ...extra,
  }
  return { deps, calls, snapshots }
}

describe('a queue that goes well', () => {
  it('reviews every artefact, one at a time and in order', async () => {
    const { deps, calls } = fake({})
    const out = await runReviewQueue(queue, deps)
    expect(calls.map((c) => c.id)).toEqual(['A', 'B', 'C'])
    expect(out.run.items.map((i) => i.state)).toEqual(['done', 'done', 'done'])
    expect(out.run.finished).toBe(true)
    expect(out.run.stoppedBy).toBeNull()
    expect(headline(out.run)).toBe('Reviewed all 3')
    expect(out.paused).toBeNull()
    expect(out.remaining).toEqual([])
  })

  it('never has two reviews in flight at once', async () => {
    let inFlight = 0, peak = 0
    const { deps } = fake({}, {
      async review(id) { inFlight += 1; peak = Math.max(peak, inFlight); await new Promise((r) => setTimeout(r, 2)); inFlight -= 1; return done(id) },
    })
    await runReviewQueue(queue, deps)
    expect(peak).toBe(1)
  })

  it('shows each artefact as reviewing while it is being reviewed, and each verdict the moment it is ready', async () => {
    const { deps, snapshots } = fake({ B: done('B', { verdict: 'revise', findings: [{ severity: 'high', target: 'x', problem: 'p', fix: 'f' }] }) })
    await runReviewQueue(queue, deps)
    const states = snapshots.map((s) => s.items.map((i) => i.state[0]).join(''))        // w=waiting r=reviewing d=done
    expect(states[0]).toBe('www')
    expect(states).toContain('rww')
    expect(states).toContain('drw')
    expect(states).toContain('ddr')
    expect(states[states.length - 1]).toBe('ddd')
    const afterB = snapshots.find((s) => s.items[1].state === 'done')!
    expect(afterB.items[1]).toMatchObject({ verdict: 'revise', highFindings: 1, label: 'independent', costUsd: 0.01 })
    expect(afterB.items[2].state).not.toBe('done')                                       // C was not shown as reviewed before it was
  })

  it('counts and costs as it goes, and a cost that is unknown stays unknown', async () => {
    const { deps } = fake({ A: done('A', { cost_usd: 0.02 }), B: done('B', { cost_usd: 0.03 }) })
    const out = await runReviewQueue(queue, deps)
    expect(costSoFar(out.run)).toBeCloseTo(0.06)
    const unpriced = await runReviewQueue(queue, fake({ B: done('B', { cost_usd: null }) }).deps)
    expect(costSoFar(unpriced.run)).toBeNull()
  })

  it('an empty queue finishes at once and calls nothing', async () => {
    const { deps, calls } = fake({})
    const out = await runReviewQueue([], deps)
    expect(calls).toEqual([])
    expect(out.run.finished).toBe(true)
    expect(headline(out.run)).toBe('Reviewed all 0')
  })

  it('asks the screen to refresh after each artefact, and a refresh that throws does not stop the reviews', async () => {
    let refreshed = 0
    const { deps, calls } = fake({}, { async afterEach() { refreshed += 1; throw new Error('refresh failed') } })
    const out = await runReviewQueue(queue, deps)
    expect(refreshed).toBe(3)
    expect(calls).toHaveLength(3)
    expect(out.run.items.every((i) => i.state === 'done')).toBe(true)
  })
})

describe('stopping', () => {
  it('stops before the next artefact when asked, lets the one in flight finish, and says the rest were not reviewed', async () => {
    let stop = false
    const asked: string[] = []
    const { deps } = fake({}, {
      shouldStop: () => stop,
      async review(id) { asked.push(id); if (id === 'B') stop = true; return done(id) },       // the person presses Stop while B is being reviewed
    })
    const out = await runReviewQueue(queue, deps)
    expect(asked).toEqual(['A', 'B'])                                                       // C was never sent to a model
    expect(out.run.items.map((i) => i.state)).toEqual(['done', 'done', 'not_run'])          // B finished; C never started
    expect(out.run.stoppedBy).toBe('you')
    expect(out.run.items[2].note).toBe('You stopped before this one.')
    expect(headline(out.run)).toBe('Stopped: 2 of 3 reviewed')
  })

  it('a stop asked for before anything started reviews nothing', async () => {
    const { deps, calls } = fake({}, { shouldStop: () => true })
    const out = await runReviewQueue(queue, deps)
    expect(calls).toEqual([])
    expect(out.run.items.every((i) => i.state === 'not_run')).toBe(true)
    expect(headline(out.run)).toBe('Stopped: 0 of 3 reviewed')
  })

  it('requesting a stop is shown while still going, and has no effect on a finished run', () => {
    const run = startRun(queue)
    expect(headline(requestStop(run))).toBe('Stopping after this one: 0 of 3 reviewed')
    const over = finishRun(run, null)
    expect(requestStop(over)).toBe(over)
  })
})

describe('a reviewer that cannot run', () => {
  it('pauses the queue on that artefact, keeps what was done, and returns what is left, starting with the one that paused', async () => {
    const { deps, calls } = fake({ B: pausedAnswer('B') })
    const out = await runReviewQueue(queue, deps)
    expect(out.run.items.map((i) => i.state)).toEqual(['done', 'paused', 'not_run'])
    expect(out.run.stoppedBy).toBe('paused')
    expect(out.paused?.artefact_id).toBe('B')
    expect(out.remaining.map((q) => q.id)).toEqual(['B', 'C'])
    expect(out.excluded).toEqual(['sonnet'])
    expect(calls.map((c) => c.id)).toEqual(['A', 'B'])                                    // C was not tried against a reviewer that just failed
    expect(headline(out.run)).toBe('Paused after 1 of 3: a reviewer is needed')
    expect(out.run.items[2].note).toBe('Waiting for you to choose a reviewer.')
  })

  it('continuing with a chosen family reviews the rest with it and tells the server which slots already failed', async () => {
    const first = await runReviewQueue(queue, fake({ B: pausedAnswer('B') }).deps)
    const { deps, calls } = fake({})
    const out = await runReviewQueue(first.remaining, deps, { slot: 'openai', exclude: first.excluded })
    expect(calls).toEqual([{ id: 'B', choice: { slot: 'openai', exclude: ['sonnet'] } }, { id: 'C', choice: { slot: 'openai', exclude: ['sonnet'] } }])
    expect(out.run.items.every((i) => i.state === 'done')).toBe(true)
  })

  it('a chosen family that fails too is added to the excluded list, never forgotten', async () => {
    const out = await runReviewQueue([{ id: 'B', name: 'B' }], fake({ B: pausedAnswer('B', 'openai') }).deps, { slot: 'openai', exclude: ['sonnet'] })
    expect(out.excluded.sort()).toEqual(['openai', 'sonnet'])
  })

  it('without a chosen family the server is asked for its own default, with no slot sent', async () => {
    const { deps, calls } = fake({})
    await runReviewQueue(queue, deps)
    expect(calls.every((c) => Object.keys(c.choice).length === 0)).toBe(true)
  })
})

describe('a review that goes wrong', () => {
  it('one artefact failing for its own reason does not stop the others', async () => {
    const { deps, calls } = fake({ B: new ServerRefused(422, 'the review of B could not be produced: the reply failed its checks') })
    const out = await runReviewQueue(queue, deps)
    expect(out.run.items.map((i) => i.state)).toEqual(['done', 'failed', 'done'])
    expect(out.run.items[1].note).toBe('the review of B could not be produced: the reply failed its checks')
    expect(calls.map((c) => c.id)).toEqual(['A', 'B', 'C'])
    expect(headline(out.run)).toBe('Finished: 2 of 3 reviewed, 1 could not be')
    expect(out.run.stoppedBy).toBeNull()
  })

  it.each([[400], [404], [409]])('a %i stops the whole queue, because every other artefact would fail the same way', async (status) => {
    const { deps, calls } = fake({ A: new ServerRefused(status, 'This project is archived; restore it first.') })
    const out = await runReviewQueue(queue, deps)
    expect(calls.map((c) => c.id)).toEqual(['A'])
    expect(out.run.items.map((i) => i.state)).toEqual(['failed', 'not_run', 'not_run'])
    expect(out.run.stoppedBy).toBe('problem')
    expect(out.run.items[1].note).toBe('Not run: an earlier problem stopped the queue.')
    expect(headline(out.run)).toBe('Stopped by a problem: 0 of 3 reviewed')
  })

  it('a backend that is not running stops the queue too', async () => {
    const out = await runReviewQueue(queue, fake({ B: new BackendUnreachable() }).deps)
    expect(out.run.items.map((i) => i.state)).toEqual(['done', 'failed', 'not_run'])
    expect(out.run.stoppedBy).toBe('problem')
  })

  it('which errors stop a queue', () => {
    expect(stopsTheQueue(new ServerRefused(409, 'x'))).toBe(true)
    expect(stopsTheQueue(new ServerRefused(400, 'x'))).toBe(true)
    expect(stopsTheQueue(new ServerRefused(404, 'x'))).toBe(true)
    expect(stopsTheQueue(new BackendUnreachable())).toBe(true)
    expect(stopsTheQueue(new ServerRefused(422, 'x'))).toBe(false)
    expect(stopsTheQueue(new ServerRefused(500, 'x'))).toBe(false)
    expect(stopsTheQueue(new Error('anything else'))).toBe(false)
    expect(stopsTheQueue('not even an error')).toBe(false)
  })

  it('a failure that is not an Error object still gets a sentence', async () => {
    const out = await runReviewQueue([{ id: 'A', name: 'A' }], { ...fake({}).deps, review: async () => { throw 'oops' } })
    expect(out.run.items[0]).toMatchObject({ state: 'failed', note: 'The review could not be run.' })
  })
})

describe('the numbers on the screen', () => {
  it('tally counts each state', () => {
    let run = startRun(queue)
    run = markDone(markReviewing(run, 'A'), 'A', done('A') as never)
    run = markReviewing(run, 'B')
    expect(tally(run)).toEqual({ total: 3, done: 1, failed: 0, reviewing: 1, waiting: 1, paused: 0, notRun: 0 })
  })
  it('the headline counts up while going, and never past the total', () => {
    let run = startRun(queue)
    expect(headline(run)).toBe('Reviewing 1 of 3')
    run = markDone(markReviewing(run, 'A'), 'A', done('A') as never)
    expect(headline(run)).toBe('Reviewing 2 of 3')
    run = markDone(markDone(run, 'B', done('B') as never), 'C', done('C') as never)
    expect(headline(run)).toBe('Reviewing 3 of 3')
  })
  it('high findings are counted from the answer', () => {
    const run = markDone(startRun(queue), 'A', done('A', { findings: [{ severity: 'high', target: 't', problem: 'p', fix: 'f' }, { severity: 'low', target: 't', problem: 'p', fix: 'f' }, { severity: 'high', target: 't', problem: 'p', fix: 'f' }] }) as never)
    expect(run.items[0].highFindings).toBe(2)
  })
  it('finishing a run leaves no row saying waiting', () => {
    for (const by of [null, 'you', 'problem', 'paused'] as const) {
      expect(finishRun(startRun(queue), by).items.some((i) => i.state === 'waiting')).toBe(false)
    }
  })
  it('does not change the run it was given', () => {
    const run = startRun(queue)
    const before = JSON.stringify(run)
    markReviewing(run, 'A'); finishRun(run, 'you'); requestStop(run)
    expect(JSON.stringify(run)).toBe(before)
  })
})
