import { describe, expect, it } from 'vitest'
import { DEFAULT_LOOK, LOOKS, LOOK_KEY, LOOK_LABEL, chooseLook, isLook, pictureFor, readLook, saveLook, startLook, type LookStore } from './look'

const memory = (initial: Record<string, string> = {}): LookStore & { data: Record<string, string> } => {
  const data = { ...initial }
  return { data, getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = v } }
}
const refusing: LookStore = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } }

describe('the two looks', () => {
  it('are draw.io and Notion, in that order, with the draw.io look as the default', () => {
    expect([...LOOKS]).toEqual(['drawio', 'notion']); expect(DEFAULT_LOOK).toBe('drawio')
    expect(LOOK_LABEL).toEqual({ drawio: 'draw.io', notion: 'Notion' })
  })
  it('isLook accepts only those two', () => {
    expect(isLook('drawio') && isLook('notion')).toBe(true)
    for (const bad of ['', 'Notion', 'neon', null, undefined, 3, {}]) expect(isLook(bad)).toBe(false)
  })
})

describe('remembering a look', () => {
  it('reads what was saved, and the default when nothing was', () => {
    expect(readLook(memory({ [LOOK_KEY]: 'notion' }))).toBe('notion')
    expect(readLook(memory())).toBe('drawio')
  })
  it('a saved value that is not one of ours is ignored, not shown', () => {
    expect(readLook(memory({ [LOOK_KEY]: '<script>' }))).toBe('drawio'); expect(readLook(memory({ [LOOK_KEY]: 'neon' }))).toBe('drawio')
  })
  it('a browser with no storage, or one that refuses, gives the default and never throws', () => {
    expect(readLook(null)).toBe('drawio'); expect(readLook(refusing)).toBe('drawio')
  })
  it('saving writes the look under one key and says it worked', () => {
    const s = memory()
    expect(saveLook(s, 'notion')).toBe(true); expect(s.data).toEqual({ [LOOK_KEY]: 'notion' }); expect(LOOK_KEY).toBe('sdlc.diagram.look')
  })
  it('saving into nothing, or into a browser that refuses, says it did not and never throws', () => {
    expect(saveLook(null, 'notion')).toBe(false); expect(saveLook(refusing, 'notion')).toBe(false)
  })
  it('a look that is not one of ours is never saved', () => {
    const s = memory(); expect(saveLook(s, 'neon' as never)).toBe(false); expect(s.data).toEqual({})
  })
})

describe('choosing the picture', () => {
  const both = { drawio: '<svg>a</svg>', notion: '<svg>b</svg>' }
  it('gives the picture for the chosen look', () => { expect(pictureFor(both, 'notion')).toBe('<svg>b</svg>'); expect(pictureFor(both, 'drawio')).toBe('<svg>a</svg>') })
  it('falls back to the default look, then to any picture, then to nothing', () => {
    expect(pictureFor({ drawio: '<svg>a</svg>' }, 'notion')).toBe('<svg>a</svg>')
    expect(pictureFor({ other: '<svg>z</svg>' }, 'notion')).toBe('<svg>z</svg>')
    expect(pictureFor({}, 'notion')).toBeNull(); expect(pictureFor(null, 'drawio')).toBeNull()
  })
})

describe('starting and choosing', () => {
  it('a look asked for wins over the remembered one, which wins over the default', () => {
    expect(startLook('notion', memory({ [LOOK_KEY]: 'drawio' }))).toBe('notion')
    expect(startLook(undefined, memory({ [LOOK_KEY]: 'notion' }))).toBe('notion')
    expect(startLook(undefined, memory())).toBe('drawio'); expect(startLook(undefined, null)).toBe('drawio')
    expect(startLook('neon' as never, memory({ [LOOK_KEY]: 'notion' }))).toBe('notion')
  })
  it('choosing a look returns it and remembers it, and a browser that refuses does not stop the choice', () => {
    const s = memory(); expect(chooseLook(s, 'notion')).toBe('notion'); expect(s.data[LOOK_KEY]).toBe('notion')
    expect(chooseLook(refusing, 'notion')).toBe('notion'); expect(chooseLook(null, 'drawio')).toBe('drawio')
  })
})
