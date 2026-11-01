import { describe, expect, it } from 'vitest'
import { copyText } from './clipboard'

describe('copyText', () => {
  it('writes the text to the clipboard and says it was copied', async () => {
    const written: string[] = []
    expect(await copyText('fix it', { clipboard: { writeText: async (t) => { written.push(t) } } })).toBe(true)
    expect(written).toEqual(['fix it'])
  })
  it('when the clipboard refuses, the old route is tried with the same text', async () => {
    const legacy: string[] = []
    const ok = await copyText('fix it', { clipboard: { writeText: async () => { throw new Error('denied') } }, legacyCopy: (t) => { legacy.push(t); return true } })
    expect(ok).toBe(true); expect(legacy).toEqual(['fix it'])
  })
  it('when there is no clipboard (an insecure page) the old route is used', async () => {
    const legacy: string[] = []
    expect(await copyText('fix it', { clipboard: null, legacyCopy: (t) => { legacy.push(t); return true } })).toBe(true)
    expect(legacy).toEqual(['fix it'])
  })
  it('it never claims success when nothing was copied', async () => {
    expect(await copyText('fix it', { clipboard: null, legacyCopy: () => false })).toBe(false)
    expect(await copyText('fix it', { clipboard: { writeText: async () => { throw new Error('denied') } }, legacyCopy: () => false })).toBe(false)
  })
  it('nothing is copied for empty text, and neither route is tried', async () => {
    let tried = 0
    expect(await copyText('', { clipboard: { writeText: async () => { tried += 1 } }, legacyCopy: () => { tried += 1; return true } })).toBe(false)
    expect(tried).toBe(0)
  })
  it('the clipboard is not touched when it works, so the old route is not also run', async () => {
    let legacy = 0
    await copyText('x', { clipboard: { writeText: async () => {} }, legacyCopy: () => { legacy += 1; return true } })
    expect(legacy).toBe(0)
  })
})
