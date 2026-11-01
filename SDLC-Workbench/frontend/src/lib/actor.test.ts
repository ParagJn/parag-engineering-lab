import { describe, expect, it } from 'vitest'
import { ACTOR_KEY, cleanName, loadName, MAX_NAME, nameProblem, saveName, type KeyValueStore } from './actor'

const memory = (): KeyValueStore & { data: Record<string, string> } => {
  const data: Record<string, string> = {}
  return { data, getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = v } }
}
const broken: KeyValueStore = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } }

describe('actor name', () => {
  it('is tidied: spaces collapsed, control characters turned into spaces', () => {
    expect(cleanName('  Parag    Jain ')).toBe('Parag Jain')
    expect(cleanName('Pa\u0000rag\u0007 J')).toBe('Pa rag J')
  })
  it.each([['', 'Enter a name'], ['   ', 'Enter a name'], ['x'.repeat(MAX_NAME + 1), 'characters or fewer'], ['system', 'reserved'], ['System', 'reserved'],
    ['human:ann', 'reserved'], ['agent:x@y', 'reserved']])('refuses %j', (raw, fragment) => {
    expect(nameProblem(raw)).toContain(fragment)
  })
  it.each(['Parag', 'Parag Jain', "O'Brien", 'José', '李雷', 'x'.repeat(MAX_NAME)])('accepts %j', (raw) => {
    expect(nameProblem(raw)).toBeNull()
  })
  it('round-trips through storage', () => {
    const store = memory()
    expect(saveName(store, '  Parag  ')).toBe(true)
    expect(store.data[ACTOR_KEY]).toBe('Parag')
    expect(loadName(store)).toBe('Parag')
  })
  it('does not save a bad name', () => {
    const store = memory()
    expect(saveName(store, 'system')).toBe(false)
    expect(store.data[ACTOR_KEY]).toBeUndefined()
  })
  it('works without any storage at all, and when storage throws', () => {
    expect(loadName(null)).toBe('')
    expect(saveName(null, 'Parag')).toBe(false)
    expect(loadName(broken)).toBe('')
    expect(saveName(broken, 'Parag')).toBe(false)
  })
  it('a stored value that is not a valid name is cleaned on the way out', () => {
    const store = memory()
    store.data[ACTOR_KEY] = '  a\u0000b  '
    expect(loadName(store)).toBe('a b')
  })
})
