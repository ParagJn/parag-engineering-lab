// The Download buttons of the Build instruction set (S19). A static render cannot press a button, but InstructionFiles is a plain function component
// with no hooks, so it is called directly here and the buttons in the elements it returns are pressed with the save function stood in for.
import type { ReactElement, ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const saved: Array<{ name: string; text: string }> = []
vi.mock('../lib/download', () => ({ saveText: (name: string, text: string) => { saved.push({ name, text }) } }))

import { InstructionFiles } from './InstructionFiles'

type El = ReactElement<{ children?: ReactNode; onClick?: () => void; 'aria-label'?: string }>

function find(node: ReactNode, test: (e: El) => boolean, out: El[] = []): El[] {
  if (Array.isArray(node)) { node.forEach((n) => find(n, test, out)); return out }
  if (node && typeof node === 'object' && 'props' in node) {
    const el = node as El
    if (test(el)) out.push(el)
    find(el.props.children, test, out)
  }
  return out
}

const buttons = (body: string) => find(InstructionFiles({ body }), (e) => e.type === 'button')
const BODY = '## Overview\nx\n\n## Instructions\n=== FILE: 00-foundation.md ===\n# Foundation\n\n## Goal\nA service.\n\n=== FILE: a+b.md ===\n# Odd name\n'

describe('pressing a file\'s Download button', () => {
  beforeEach(() => { saved.length = 0 })
  it('there is one button per file', () => { expect(buttons(BODY)).toHaveLength(2) })
  it('each saves exactly its own file\'s text, not the whole set\'s', () => {
    buttons(BODY).forEach((b) => b.props.onClick!())
    expect(saved).toEqual([{ name: '00-foundation.md', text: '# Foundation\n\n## Goal\nA service.\n' }, { name: 'a_b.md', text: '# Odd name\n' }])
  })
  it('the button\'s label names the file as it will be saved, not the name in the mark', () => {
    expect(buttons(BODY).map((b) => b.props['aria-label'])).toEqual(['Download 00-foundation.md', 'Download a_b.md'])
  })
  it('a set with no files has no button', () => { expect(buttons('## Overview\nnothing\n')).toHaveLength(0) })
})

describe('pressing a file\'s Edit this file button (S19f)', () => {
  const edit = (body: string, onEditFile: (n: string) => void) => find(InstructionFiles({ body, onEditFile }), (e) => e.type === 'button' && String(e.props['aria-label'] ?? '').startsWith('Edit '))
  it('each button asks to edit its own file, by the name the server gave it', () => {
    const asked: string[] = []
    edit(BODY, (n) => asked.push(n)).forEach((b) => b.props.onClick!())
    expect(asked).toEqual(['00-foundation.md', 'a+b.md'])
  })
  it('there is one such button per editable file, and none for the design index', () => {
    const withIndex = BODY + '\n=== FILE: 02-design-index.md ===\n# Index\n'
    expect(edit(withIndex, () => {}).map((b) => b.props['aria-label'])).toEqual(['Edit 00-foundation.md', 'Edit a+b.md'])
  })
  it('with no handler there is no such button at all', () => {
    expect(find(InstructionFiles({ body: BODY }), (e) => e.type === 'button' && String(e.props['aria-label'] ?? '').startsWith('Edit '))).toHaveLength(0)
  })
})

