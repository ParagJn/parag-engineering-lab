// "Review all" as a visible queue (S12c follow-up). One artefact at a time, through the same single-artefact review as the Review button,
// so each verdict appears the moment it is ready, the person can stop between artefacts, and a reviewer that cannot run asks for a choice
// instead of failing the rest. The loop is a pure function of what it is given, so it can be tested with a fake reviewer.
import { BackendUnreachable, ServerRefused, type ReviewAnswer, type ReviewPaused, type Verdict } from '../api'

export type ItemState = 'waiting' | 'reviewing' | 'done' | 'failed' | 'paused' | 'not_run'

export interface RunItem {
  id: string
  name: string
  state: ItemState
  verdict: Verdict | null
  label: string | null
  highFindings: number
  costUsd: number | null
  /** The server's sentence for a failure, or why it was not run. Shown as text. */
  note: string | null
}

export type StoppedBy = 'you' | 'problem' | 'paused' | null

export interface ReviewRun {
  items: RunItem[]
  stopRequested: boolean
  finished: boolean
  stoppedBy: StoppedBy
}

export interface QueueItem { id: string; name: string }

export function startRun(queue: QueueItem[]): ReviewRun {
  return {
    items: queue.map((q) => ({ id: q.id, name: q.name, state: 'waiting', verdict: null, label: null, highFindings: 0, costUsd: null, note: null })),
    stopRequested: false, finished: false, stoppedBy: null,
  }
}

const change = (run: ReviewRun, id: string, patch: Partial<RunItem>): ReviewRun => ({ ...run, items: run.items.map((i) => (i.id === id ? { ...i, ...patch } : i)) })

export const markReviewing = (run: ReviewRun, id: string) => change(run, id, { state: 'reviewing', note: null })
export const markFailed = (run: ReviewRun, id: string, note: string) => change(run, id, { state: 'failed', note })
export const markPaused = (run: ReviewRun, id: string) => change(run, id, { state: 'paused', note: 'The reviewer could not run: choose another model family below.' })
export const markDone = (run: ReviewRun, id: string, answer: Extract<ReviewAnswer, { paused: false }>) =>
  change(run, id, {
    state: 'done', verdict: answer.verdict, label: answer.independence.label, costUsd: answer.cost_usd, note: null,
    highFindings: answer.findings.filter((f) => f.severity === 'high').length,
  })
export const requestStop = (run: ReviewRun): ReviewRun => (run.finished ? run : { ...run, stopRequested: true })

/** Close the run. Anything still waiting is shown as not reviewed, with the reason, so no row is left saying "waiting" for ever. */
export function finishRun(run: ReviewRun, stoppedBy: StoppedBy): ReviewRun {
  const why = stoppedBy === 'you' ? 'You stopped before this one.' : stoppedBy === 'paused' ? 'Waiting for you to choose a reviewer.' : stoppedBy === 'problem' ? 'Not run: an earlier problem stopped the queue.' : 'Not run.'
  return { ...run, finished: true, stoppedBy, items: run.items.map((i) => (i.state === 'waiting' ? { ...i, state: 'not_run', note: why } : i)) }
}

export function tally(run: ReviewRun) {
  const count = (s: ItemState) => run.items.filter((i) => i.state === s).length
  return { total: run.items.length, done: count('done'), failed: count('failed'), reviewing: count('reviewing'), waiting: count('waiting'), paused: count('paused'), notRun: count('not_run') }
}

/** Money spent so far by the reviews that finished. Unknown (null) the moment one of them had no price, never quietly low. */
export function costSoFar(run: ReviewRun): number | null {
  const done = run.items.filter((i) => i.state === 'done')
  return done.some((i) => i.costUsd === null) ? null : done.reduce((sum, i) => sum + (i.costUsd ?? 0), 0)
}

export function headline(run: ReviewRun): string {
  const t = tally(run)
  const settled = t.done + t.failed
  if (!run.finished) {
    if (run.stopRequested) return `Stopping after this one: ${t.done} of ${t.total} reviewed`
    return `Reviewing ${Math.min(settled + 1, t.total)} of ${t.total}`
  }
  if (run.stoppedBy === 'paused') return `Paused after ${t.done} of ${t.total}: a reviewer is needed`
  if (run.stoppedBy === 'you') return `Stopped: ${t.done} of ${t.total} reviewed`
  if (run.stoppedBy === 'problem') return `Stopped by a problem: ${t.done} of ${t.total} reviewed`
  return t.failed > 0 ? `Finished: ${t.done} of ${t.total} reviewed, ${t.failed} could not be` : `Reviewed all ${t.total}`
}

/** A problem that makes the next artefact pointless to try: the project is archived, the phase is the wrong state, nobody is named, or the backend is gone.
 *  A review the reviewer's reply made unusable (a 422) is only that artefact's problem, so the queue carries on. */
export function stopsTheQueue(error: unknown): boolean {
  if (error instanceof BackendUnreachable) return true
  return error instanceof ServerRefused && [400, 404, 409].includes(error.status)
}

export interface QueueDeps {
  review(id: string, choice: { slot?: string; exclude?: string[] }): Promise<ReviewAnswer>
  shouldStop(): boolean
  onUpdate(run: ReviewRun): void
  /** Called after each artefact settles, so the screen can refresh its chips. A failure here never stops the queue. */
  afterEach?(): Promise<void> | void
}

export interface QueueOutcome {
  run: ReviewRun
  /** Set when the reviewer could not run: the options to choose from. */
  paused: ReviewPaused | null
  /** The artefacts still to do, starting with the one that paused (so choosing a family continues from there). */
  remaining: QueueItem[]
  /** Every slot that has failed so far, to be passed back so the same one is never offered or tried again. */
  excluded: string[]
}

export async function runReviewQueue(queue: QueueItem[], deps: QueueDeps, choice: { slot?: string; exclude?: string[] } = {}): Promise<QueueOutcome> {
  let run = startRun(queue)
  deps.onUpdate(run)
  let paused: ReviewPaused | null = null
  let remaining: QueueItem[] = []
  let excluded = [...(choice.exclude ?? [])]
  let stoppedBy: StoppedBy = null

  for (let index = 0; index < queue.length; index += 1) {
    const item = queue[index]
    if (deps.shouldStop()) { stoppedBy = 'you'; break }
    run = markReviewing(run, item.id)
    deps.onUpdate(run)
    try {
      const answer = await deps.review(item.id, choice.slot ? { slot: choice.slot, exclude: excluded } : {})
      if (answer.paused) {
        run = markPaused(run, item.id)
        paused = answer
        remaining = queue.slice(index)
        excluded = [...new Set([...excluded, answer.slot])]
        stoppedBy = 'paused'
        break
      }
      run = markDone(run, item.id, answer)
    } catch (error) {
      run = markFailed(run, item.id, error instanceof Error ? error.message : 'The review could not be run.')
      if (stopsTheQueue(error)) { stoppedBy = 'problem'; break }
    }
    deps.onUpdate(run)
    try { await deps.afterEach?.() } catch { /* a refresh that fails must not stop the reviews */ }
  }
  run = finishRun(run, stoppedBy)
  deps.onUpdate(run)
  return { run, paused, remaining, excluded }
}
