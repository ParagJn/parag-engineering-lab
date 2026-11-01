import { describe, expect, it } from 'vitest'
import { EXTENSIONS, MAX_FILE_BYTES, MAX_STAGED, extensionOf, fileProblem, pastedFilename, pasteProblem } from './documents'

describe('names for pasted text', () => {
  it.each([
    ['', 'pasted-notes.md'], ['   ', 'pasted-notes.md'], ['policy', 'policy.md'], ['policy.md', 'policy.md'], ['notes.TXT', 'notes.TXT'],
    ['a/b/c.md', 'c.md'], ['..\\\\..\\\\etc\\\\passwd', 'passwd.md'], ['.hidden', 'hidden.md'], ['two  spaces here', 'two spaces here.md'],
    ['bell\u0007name', 'bell name.md'], ['doc.markdown', 'doc.markdown'], ['report.docx', 'report.docx.md'],
  ])('%j becomes %j', (raw, expected) => { expect(pastedFilename(raw)).toBe(expected) })
  it('is cut to a sensible length and still ends in an extension', () => {
    const out = pastedFilename('x'.repeat(500))
    expect(out.length).toBeLessThanOrEqual(103)
    expect(out.endsWith('.md')).toBe(true)
  })
  it('never contains a path separator', () => { expect(pastedFilename('a/b\\\\c')).not.toMatch(/[\\\\/]/) })
})

describe('what a file may be', () => {
  it('knows the extensions the server accepts', () => { expect([...EXTENSIONS].sort()).toEqual(['docx', 'markdown', 'md', 'pdf', 'txt']) })
  it.each([['a.md', 'md'], ['A.PDF', 'pdf'], ['x.tar.gz', 'gz'], ['noext', ''], ['.md', 'md']])('the extension of %j is %j', (n, e) => { expect(extensionOf(n)).toBe(e) })
  it('accepts an ordinary file', () => { expect(fileProblem('policy.md', 100, 0)).toBeNull() })
  it('refuses an unsupported type, naming it and the allowed ones', () => {
    const why = fileProblem('virus.exe', 100, 0)!
    expect(why).toContain('virus.exe')
    expect(why).toContain('.md')
  })
  it('refuses an empty file', () => { expect(fileProblem('a.md', 0, 0)).toContain('is empty') })
  it('refuses a file over the limit, and accepts one exactly at it', () => {
    expect(fileProblem('a.md', MAX_FILE_BYTES + 1, 0)).toContain('larger than the 10 MB limit')
    expect(fileProblem('a.md', MAX_FILE_BYTES, 0)).toBeNull()
  })
  it('refuses the eleventh staged document, and accepts the tenth', () => {
    expect(fileProblem('a.md', 5, MAX_STAGED - 1)).toBeNull()
    expect(fileProblem('a.md', 5, MAX_STAGED)).toContain(`up to ${MAX_STAGED}`)
  })
  it('the type is checked before the size', () => { expect(fileProblem('a.exe', 0, 0)).toContain('not a supported file type') })
})

describe('pasted text', () => {
  it('nothing, or only spaces and line breaks, is not a document', () => {
    for (const t of ['', '   ', '\n\n\t']) expect(pasteProblem(t)).toBe('Paste some text first.')
  })
  it('anything else is', () => { expect(pasteProblem('x')).toBeNull() })
})
