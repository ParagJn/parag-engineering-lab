import { describe, expect, it } from 'vitest'
import { loadPaths, savePaths, type KeyValueStore } from './verifyPaths'

const memory = (): KeyValueStore & { data: Map<string, string> } => { const data = new Map<string, string>(); return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => { data.set(k, v) } } }

describe('the remembered folders', () => {
  it('come back as they were saved, for the project they were saved for', () => {
    const s = memory()
    savePaths(s, 'p1', { backend: '/a/back', frontend: '/a/front' })
    expect(loadPaths(s, 'p1')).toEqual({ backend: '/a/back', frontend: '/a/front' }); expect(loadPaths(s, 'p2')).toEqual({ backend: '', frontend: '' })
  })
  it('are empty when nothing was saved, when there is no store, or when what was saved is damaged', () => {
    const s = memory()
    expect(loadPaths(s, 'p1')).toEqual({ backend: '', frontend: '' }); expect(loadPaths(null, 'p1')).toEqual({ backend: '', frontend: '' })
    s.data.set('sdlc.verify.paths.p1', '{not json'); expect(loadPaths(s, 'p1')).toEqual({ backend: '', frontend: '' })
    s.data.set('sdlc.verify.paths.p1', JSON.stringify({ backend: 5, frontend: ['x'] })); expect(loadPaths(s, 'p1')).toEqual({ backend: '', frontend: '' })
  })
  it('are cut to a thousand characters, as the server would refuse more', () => {
    const s = memory()
    savePaths(s, 'p1', { backend: 'a'.repeat(1500), frontend: 'b'.repeat(1500) })
    expect(loadPaths(s, 'p1').backend).toHaveLength(1000); expect(loadPaths(s, 'p1').frontend).toHaveLength(1000)
    s.data.set('sdlc.verify.paths.p2', JSON.stringify({ backend: 'c'.repeat(1500), frontend: '' })); expect(loadPaths(s, 'p2').backend).toHaveLength(1000)
  })
  it('keep what was saved to a thousand characters in the store itself, not only when read back', () => {
    const s = memory()
    savePaths(s, 'p1', { backend: 'a'.repeat(1500), frontend: 'b'.repeat(1200) })
    const stored = JSON.parse(s.data.get('sdlc.verify.paths.p1')!)
    expect(stored.backend).toHaveLength(1000); expect(stored.frontend).toHaveLength(1000)
  })
  it('never fail the page when the store is full or blocked', () => {
    const blocked: KeyValueStore = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('full') } }
    expect(() => savePaths(blocked, 'p1', { backend: 'x', frontend: '' })).not.toThrow(); expect(loadPaths(blocked, 'p1')).toEqual({ backend: '', frontend: '' })
    expect(() => savePaths(null, 'p1', { backend: 'x', frontend: '' })).not.toThrow()
  })
})
