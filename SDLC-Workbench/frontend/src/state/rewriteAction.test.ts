// "Rewrite everything" (2026-11-04): a button the server offers once a running phase has something written. It starts a run that writes EVERY artefact again.
import { describe, expect, it, vi } from 'vitest'
import { ACTIONS } from '../api'
import { actionSpecs, pressRoute } from '../lib/phaseActions'
import { performAction, rewriteOptions, saveEditOf, startsARun } from './useProjectScreen'

const phase = (status: string, allowed: string[]) => ({ key: 'build', name: 'Build', status, allowed_actions: allowed }) as never

describe('the rewrite action', () => {
  it('is one of the actions the server can name, placed between run and finish', () => {
    expect([...ACTIONS]).toEqual(['run', 'rewrite', 'finish', 'approve', 'request_changes', 'reopen'])
    expect(ACTIONS.indexOf('rewrite' as never)).toBeGreaterThan(ACTIONS.indexOf('run'))
    expect(ACTIONS.indexOf('rewrite' as never)).toBeLessThan(ACTIONS.indexOf('finish'))
  })
  it('says what it does and what it costs, in each mode', () => {
    const live = actionSpecs(phase('running', ['rewrite']), 'live')[0]
    const replay = actionSpecs(phase('running', ['rewrite']), 'replay')[0]
    expect(live).toMatchObject({ action: 'rewrite', label: 'Rewrite everything', live: true })
    expect(live.hint).toContain('every artefact')
    expect(live.hint).toContain('old versions are kept')
    expect(live.hint).toContain('costs money')
    expect(replay.hint).toContain('free and offline')
    expect(replay.hint).not.toContain('costs money')
  })
  it('is worded alongside the other actions in the server\'s order, and the plain run keeps its own wording', () => {
    const specs = actionSpecs(phase('running', ['run', 'rewrite', 'finish']), 'live')
    expect(specs.map((s) => [s.action, s.label])).toEqual([['run', 'Run it again'], ['rewrite', 'Rewrite everything'], ['finish', 'Hand to review']])
  })
  it('acts at once when pressed: it opens no form and is not the "rewrite the ones sent back" route', () => {
    for (const status of ['running', 'rejected', 'awaiting_review']) for (const notes of [0, 3]) expect(pressRoute('rewrite' as never, { status } as never, notes)).toBe('act')
  })
  it('asks the server for rewrite_all and nothing else', () => {
    expect(rewriteOptions('rewrite')).toEqual({ rewrite_all: true })
    expect(rewriteOptions('run')).toBeUndefined()
    for (const a of ['finish', 'approve', 'request_changes', 'reopen']) expect(rewriteOptions(a as never)).toBeUndefined()
  })
  it('exactly the run and the rewrite start a run; handing to review, approving, sending back and reopening do not', () => {
    expect(startsARun('run')).toBe(true)
    expect(startsARun('rewrite' as never)).toBe(true)
    for (const a of ['finish', 'approve', 'request_changes', 'reopen']) expect(startsARun(a as never)).toBe(false)
  })
  it('the button is live, so the screen lets it be pressed', () => {
    for (const mode of ['live', 'replay'] as const) expect(actionSpecs(phase('running', ['rewrite']), mode)[0].live).toBe(true)
  })
  it('the hint says the old versions are KEPT, in both modes, and never that they are replaced or lost', () => {
    for (const mode of ['live', 'replay'] as const) {
      const hint = actionSpecs(phase('running', ['rewrite']), mode)[0].hint
      expect(hint).toContain('the old versions are kept')
      expect(hint).not.toMatch(/replaced|lost|deleted|overwrit/i)
    }
  })
  it('the live hint warns of the cost, and the replay hint promises none', () => {
    expect(actionSpecs(phase('running', ['rewrite']), 'live')[0].hint).toMatch(/Calls real models: this costs money\.$/)
    expect(actionSpecs(phase('running', ['rewrite']), 'replay')[0].hint).toMatch(/free and offline\.$/)
  })
  it('the screen starts the run with that option', async () => {
    const { startFor } = await import('./useProjectScreen')
    const startRun = vi.fn().mockResolvedValue({})
    await startFor({ startRun } as never, 'p1', 'build', 'Ann', 'rewrite' as never)
    await startFor({ startRun } as never, 'p1', 'build', 'Ann', 'run' as never)
    expect(startRun.mock.calls).toEqual([['p1', 'build', 'Ann', { rewrite_all: true }], ['p1', 'build', 'Ann', undefined]])
  })
  it('pressing each button asks the server for exactly the one thing it names', async () => {
    const calls: unknown[][] = []
    const client = {
      startRun: vi.fn(async (...a: unknown[]) => { calls.push(['startRun', a[3]]) }),
      finishPhase: vi.fn(async () => { calls.push(['finishPhase']) }),
      approvePhase: vi.fn(async () => { calls.push(['approvePhase']) }),
    }
    for (const action of ['run', 'rewrite', 'finish', 'approve', 'request_changes', 'reopen']) await performAction(client as never, 'p1', 'build', 'Ann', action as never)
    expect(calls).toEqual([['startRun', undefined], ['startRun', { rewrite_all: true }], ['finishPhase'], ['approvePhase']])      // sending back and reopening have their own forms
  })
})

describe('where a save goes (S19f)', () => {
  const fake = () => { const calls: unknown[][] = []; return { calls, client: { editArtefact: vi.fn(async (...a: unknown[]) => { calls.push(['whole', ...a]) }), editFile: vi.fn(async (...a: unknown[]) => { calls.push(['file', ...a]) }) } as never } }
  it('with a file named it goes to that file, in the person\'s name, with the version they were looking at', async () => {
    const { calls, client } = fake()
    await saveEditOf(client, 'p1', 'BLD-INS-001', 7, 'UC-001-a.md', 'Ann', 'text', 'note')
    expect(calls).toEqual([['file', 'p1', 'BLD-INS-001', 'UC-001-a.md', 'Ann', 'text', 'note', 7]])
  })
  it('with no file named it saves the whole artefact, as before, and never touches the file route', async () => {
    const { calls, client } = fake()
    await saveEditOf(client, 'p1', 'REQ-PER-001', 3, null, 'Ann', 'text', 'note')
    expect(calls).toEqual([['whole', 'p1', 'REQ-PER-001', 'Ann', 'text', 'note']])
  })
  it('a refusal reaches the caller untouched so the box can list every reason', async () => {
    const boom = new Error('refused')
    await expect(saveEditOf({ editArtefact: vi.fn(), editFile: vi.fn(async () => { throw boom }) } as never, 'p', 'a', 1, 'x.md', 'Ann', 't', '')).rejects.toBe(boom)
  })
})
