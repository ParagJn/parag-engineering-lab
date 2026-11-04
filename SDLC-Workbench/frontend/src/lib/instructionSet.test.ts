import { describe, expect, it } from 'vitest'
import { INSTRUCTION_KEY, downloadOf, instructionDownloadName, isInstructionSet, lineCountOf, splitInstructionSet } from './instructionSet'

const SET = ['## Overview', 'Three files.', '', '## Files', '- INS-001 00-foundation.md: Foundation.', '', '## Instructions',
  '=== FILE: 00-foundation.md ===', '# Foundation', '', '## Goal', 'A booking service.', '',
  '=== FILE: UC-001-reserve.md ===', '', '# Reserve', '', '## Goal', 'Reserve a room.', '', ''].join('\n')

describe('cutting a saved instruction set into its files', () => {
  it('knows the one artefact type that holds a set', () => {
    expect(INSTRUCTION_KEY).toBe('build_instructions')
    expect(isInstructionSet('build_instructions')).toBe(true)
    for (const other of ['backend_code', 'low_level_design', '', 'Build_Instructions']) expect(isInstructionSet(other)).toBe(false)
  })
  it('the head is everything before the first file, and each file is cut from its own mark to the next', () => {
    const s = splitInstructionSet(SET)
    expect(s.head).toBe('## Overview\nThree files.\n\n## Files\n- INS-001 00-foundation.md: Foundation.\n\n## Instructions')
    expect(s.files.map((f) => f.name)).toEqual(['00-foundation.md', 'UC-001-reserve.md'])
    expect(s.files[0].text).toBe('# Foundation\n\n## Goal\nA booking service.\n')
    expect(s.files[1].text).toBe('# Reserve\n\n## Goal\nReserve a room.\n')
  })
  it('a file keeps exactly one newline at its end and nothing at its start, whatever blank lines surrounded it', () => {
    for (const f of splitInstructionSet(SET).files) { expect(f.text.endsWith('\n')).toBe(true); expect(f.text.endsWith('\n\n')).toBe(false); expect(f.text.startsWith('\n')).toBe(false) }
  })
  it('windows line ends and trailing blanks on a mark are read', () => {
    const s = splitInstructionSet(SET.replace(/\n/g, '\r\n').replace('=== FILE: 00-foundation.md ===', '=== FILE: 00-foundation.md ===  '))
    expect(s.files.map((f) => f.name)).toEqual(['00-foundation.md', 'UC-001-reserve.md'])
    expect(s.files[0].text).not.toContain('\r')
  })
  it('a mark must be a whole line with a name that has no spaces', () => {
    for (const odd of ['see === FILE: a.md ===', '=== FILE: my file.md ===', '=== FILE:  ===', '=== FILE: a.md === extra']) {
      const s = splitInstructionSet(`=== FILE: real.md ===\n# T\n${odd}\nmore\n`)
      expect(s.files.map((f) => f.name)).toEqual(['real.md'])
      expect(s.files[0].text).toContain(odd)
    }
  })
  it('a file named twice keeps its first text and is listed once', () => {
    const s = splitInstructionSet('=== FILE: a.md ===\nfirst\n=== FILE: a.md ===\nsecond\n=== FILE: b.md ===\nthird\n')
    expect(s.files).toEqual([{ name: 'a.md', text: 'first\n' }, { name: 'b.md', text: 'third\n' }])
  })
  it('a body with no files, an empty body and a missing body give no files and never throw', () => {
    expect(splitInstructionSet('just text').files).toEqual([])
    expect(splitInstructionSet('just text').head).toBe('just text')
    expect(splitInstructionSet('')).toEqual({ head: '', files: [] })
    expect(splitInstructionSet(undefined as unknown as string)).toEqual({ head: '', files: [] })
  })
  it('a file with nothing in it is kept, as just a newline', () => {
    expect(splitInstructionSet('=== FILE: a.md ===\n=== FILE: b.md ===\nx\n').files).toEqual([{ name: 'a.md', text: '\n' }, { name: 'b.md', text: 'x\n' }])
  })
})

describe('the name a file is downloaded under', () => {
  it('a plain .md name is kept exactly', () => {
    for (const n of ['00-foundation.md', 'UC-001-browse-rooms-and-availability.md', '99-acceptance.md', 'a.md']) expect(instructionDownloadName(n)).toBe(n)
  })
  it('anything that is not a plain .md name is made safe: no path, no odd characters, always .md', () => {
    expect(instructionDownloadName('../../etc/passwd')).toBe('etc_passwd.md')
    expect(instructionDownloadName('a b/c.md')).toBe('a_b_c.md')
    expect(instructionDownloadName('x.txt')).toBe('x.txt.md')
    expect(instructionDownloadName('')).toBe('instructions.md')
    expect(instructionDownloadName('...')).toBe('instructions.md')
    expect(instructionDownloadName('<script>.md')).toBe('script_.md')
    expect(instructionDownloadName(`${'a'.repeat(200)}.md`).length).toBeLessThanOrEqual(73)
  })
  it('counts the lines of a file', () => {
    expect(lineCountOf('')).toBe(0)
    expect(lineCountOf('a\n')).toBe(1)
    expect(lineCountOf('a\nb')).toBe(2)
    expect(lineCountOf('a\nb\n')).toBe(2)
  })
})

describe('what a Download button saves', () => {
  it('the file\'s own text under its own name', () => {
    expect(downloadOf({ name: '00-foundation.md', text: '# Foundation\n' })).toEqual({ name: '00-foundation.md', text: '# Foundation\n' })
  })
  it('an unsafe name is made safe', () => {
    expect(downloadOf({ name: 'a b.md', text: '# A\n' })).toEqual({ name: 'a_b.md', text: '# A\n' })
  })
  it('each file of a real set downloads its own text, not the whole set\'s', () => {
    const set = splitInstructionSet('## Overview\nx\n=== FILE: a.md ===\n# A\n=== FILE: c.md ===\n# C\n')
    expect(set.files.map(downloadOf)).toEqual([{ name: 'a.md', text: '# A\n' }, { name: 'c.md', text: '# C\n' }])
  })
})

describe('the parts of a set that are easy to get slightly wrong', () => {
  it('blank lines between the list of files and the first file are not part of the head', () => {
    expect(splitInstructionSet('## Overview\nx\n\n\n=== FILE: a.md ===\ny\n').head).toBe('## Overview\nx')
  })
  it('a long but plain name is kept whole, not cut to the length an unsafe name is cut to', () => {
    const long = `${'a'.repeat(75)}.md`
    expect(instructionDownloadName(long)).toBe(long)
    expect(instructionDownloadName(`${'a'.repeat(79)}.md`)).toBe(`${'a'.repeat(79)}.md`)
    expect(instructionDownloadName(`${'a'.repeat(80)}.md`).length).toBeLessThanOrEqual(73)
  })
  it('a name that starts with a dot or a dash is not kept as it is', () => {
    expect(instructionDownloadName('.hidden.md')).toBe('hidden.md')
    expect(instructionDownloadName('-x.md')).toBe('x.md')
  })
})

import { fileOfTarget, groupByFile, strayFiles } from './instructionSet'
import type { Finding } from '../api'

const finding = (target: string, severity: Finding['severity'] = 'low', extra: Partial<Finding> = {}): Finding => ({ severity, target, problem: `p ${target}`, fix: 'f', ...extra })

describe('what file and line a finding names', () => {
  it('reads a file, and a file with a line', () => {
    expect(fileOfTarget('UC-001-a.md')).toEqual({ file: 'UC-001-a.md', line: null })
    expect(fileOfTarget('UC-001-a.md:41')).toEqual({ file: 'UC-001-a.md', line: 41 })
    expect(fileOfTarget('00-foundation.md:1')).toEqual({ file: '00-foundation.md', line: 1 })
    expect(fileOfTarget('UI-HFS-001-browse.md:12345')).toEqual({ file: 'UI-HFS-001-browse.md', line: 12345 })
  })
  it('reads nothing else as a file', () => {
    for (const t of ['General', 'FR-004', 'Open questions', 'a.txt', 'a.md:', 'a.md:x', 'a.md:123456', '../a.md', '.md', 'a b.md', '']) expect(fileOfTarget(t)).toBeNull()
  })
})

describe('a review grouped by file', () => {
  it('groups the findings of one file together, in the order they came, and keeps the worst severity', () => {
    const { byFile } = groupByFile([finding('a.md:3', 'low'), finding('b.md', 'medium'), finding('a.md:9', 'high'), finding('a.md', 'medium')])
    expect([...byFile.keys()]).toEqual(['a.md', 'b.md'])
    expect(byFile.get('a.md')!.findings.map((f) => f.target)).toEqual(['a.md:3', 'a.md:9', 'a.md'])
    expect(byFile.get('a.md')!.worst).toBe('high')
    expect(byFile.get('b.md')!.worst).toBe('medium')
  })
  it('the worst severity does not depend on the order', () => {
    expect(groupByFile([finding('a.md', 'high'), finding('a.md', 'low')]).byFile.get('a.md')!.worst).toBe('high')
    expect(groupByFile([finding('a.md', 'low'), finding('a.md', 'high')]).byFile.get('a.md')!.worst).toBe('high')
    expect(groupByFile([finding('a.md', 'low'), finding('a.md', 'medium')]).byFile.get('a.md')!.worst).toBe('medium')
    expect(groupByFile([finding('a.md', 'medium'), finding('a.md', 'low')]).byFile.get('a.md')!.worst).toBe('medium')
  })
  it('keeps the whole-set findings and the ones that name no file apart from the files', () => {
    const { byFile, general, unplaced } = groupByFile([finding('General'), finding('FR-004'), finding('a.md'), finding('Open questions')])
    expect([...byFile.keys()]).toEqual(['a.md'])
    expect(general.map((f) => f.target)).toEqual(['General'])
    expect(unplaced.map((f) => f.target)).toEqual(['FR-004', 'Open questions'])
  })
  it('an empty review is empty', () => {
    const g = groupByFile([])
    expect(g.byFile.size + g.general.length + g.unplaced.length).toBe(0)
  })
  it('names the files a review mentions that the set shown beside it does not have', () => {
    const { byFile } = groupByFile([finding('a.md'), finding('gone.md')])
    expect(strayFiles(byFile, [{ name: 'a.md', text: '' }])).toEqual(['gone.md'])
    expect(strayFiles(byFile, [{ name: 'a.md', text: '' }, { name: 'gone.md', text: '' }])).toEqual([])
  })
})

import { linesOf } from './instructionSet'
describe('linesOf: the lines as a review counts them', () => {
  it('splits on newlines and drops only the empty piece after a final newline', () => {
    expect(linesOf('a\nb\n')).toEqual(['a', 'b'])
    expect(linesOf('a\nb')).toEqual(['a', 'b'])
    expect(linesOf('a\n\n')).toEqual(['a', ''])
    expect(linesOf('')).toEqual([''])
    expect(linesOf('\n')).toEqual([''])
  })
  it('reads Windows line endings as one break each', () => { expect(linesOf('a\r\nb\r\n')).toEqual(['a', 'b']) })
  it('agrees with the line count the file shows in its fold', () => {
    for (const text of ['x\n', 'x\ny\n', 'x\n\ny\n']) expect(linesOf(text).length).toBe(lineCountOf(text))
  })
})
