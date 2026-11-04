// The wiring of the checklist's choices (S21c). The row keeps its note in a `useState`; here that one hook is replaced by a plain stand-in so the row can be called as a
// function and its buttons pressed. Everything else in React is the real thing.
import type { ReactElement, ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('react', async () => {
  const real = await vi.importActual<typeof import('react')>('react')
  return { ...real, useState: (initial: unknown) => [typeof initial === 'function' ? (initial as () => unknown)() : initial, () => {}] }
})

import { decodeChecklist } from '../api'
import answered from '../contract/checklist_answered.json'
import { ChecklistPanel } from './ChecklistPanel'

type El = ReactElement<{ children?: ReactNode; onClick?: () => void; onChange?: (e: { target: { value: string } }) => void; 'aria-label'?: string; disabled?: boolean }>
const find = (n: ReactNode, test: (e: El) => boolean, out: El[] = []): El[] => {
  if (Array.isArray(n)) { n.forEach((x) => find(x, test, out)); return out }
  if (n && typeof n === 'object' && 'props' in n) { const e = n as El; if (test(e)) out.push(e); find(e.props.children, test, out) }
  return out
}
const list = decodeChecklist(answered)
const rowsOf = (props: Partial<Parameters<typeof ChecklistPanel>[0]>, calls: unknown[][]) => {
  const tree = ChecklistPanel({ checklist: list, canAnswer: true, busy: null, error: null, onAnswer: (...a) => calls.push(a), ...props })
  return find(tree, (e) => typeof e.type === 'function' && (e.type as { name?: string }).name === 'Row').map((r) => (r.type as (p: unknown) => ReactElement)(r.props))
}

describe('pressing a choice', () => {
  it('calls back with the row\'s own check, the choice, and the note already saved (not lost)', () => {
    const calls: unknown[][] = []
    const rows = rowsOf({}, calls)
    expect(rows).toHaveLength(16)
    find(rows[1], (e) => e.type === 'button').forEach((b) => b.props.onClick!())
    expect(calls).toEqual([['CHK-002', 'go', 'Fixed.'], ['CHK-002', 'no_go', 'Fixed.'], ['CHK-002', 'not_applicable', 'Fixed.']])
  })
  it('sends an empty note for a check that has none, and each row sends its own ID', () => {
    const calls: unknown[][] = []
    const rows = rowsOf({}, calls)
    find(rows[8], (e) => e.type === 'button')[1].props.onClick!(); find(rows[15], (e) => e.type === 'button')[0].props.onClick!()
    expect(calls).toEqual([['CHK-009', 'no_go', ''], ['CHK-016', 'go', '']])
  })
  it('has every button off when the person cannot answer, and only the busy row\'s when one is being saved', () => {
    const off = rowsOf({ canAnswer: false }, [])
    expect(off.every((r) => find(r, (e) => e.type === 'button').every((b) => b.props.disabled === true))).toBe(true)
    const busy = rowsOf({ busy: 'CHK-005' }, [])
    const disabled = busy.map((r) => find(r, (e) => e.type === 'button').some((b) => b.props.disabled === true))
    expect(disabled.filter(Boolean)).toHaveLength(1); expect(disabled[4]).toBe(true)
  })
})
