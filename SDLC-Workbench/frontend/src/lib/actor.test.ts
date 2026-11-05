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

import { OTHER, pickableNames, startingChoice, valueForChoice } from './actor'

describe('the names offered in the drop-down', () => {
  it('lists only active people, in list order, once each, with tidy spacing', () => {
    const users = [{ name: 'Parag', active: true }, { name: 'Gone', active: false }, { name: '  Asha   K ', active: true }, { name: 'parag', active: true }, { name: '', active: true }]
    expect(pickableNames(users)).toEqual(['Parag', 'Asha K'])
  })
  it('is empty when there is no list', () => {
    expect(pickableNames(null)).toEqual([])
    expect(pickableNames([])).toEqual([])
  })
  it('starts on the saved name when it is listed (any case, listed spelling), on someone else when it is not, and on nothing when there is no saved name', () => {
    expect(startingChoice('asha', ['Parag', 'Asha'])).toBe('Asha')
    expect(startingChoice('Visitor', ['Parag'])).toBe(OTHER)
    expect(startingChoice('', ['Parag'])).toBe('')
    expect(startingChoice('   ', ['Parag'])).toBe('')
  })
})

describe('choosing in the drop-down', () => {
  it('a listed name becomes the name; someone else or nothing leaves the box empty to type in', () => {
    expect(valueForChoice('Asha')).toBe('Asha')
    expect(valueForChoice(OTHER)).toBe('')
    expect(valueForChoice('')).toBe('')
  })
})
