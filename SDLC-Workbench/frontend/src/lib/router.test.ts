import { describe, expect, it } from 'vitest'
import { buildHash, parseHash, type Route } from './router'

const ROUTES: Route[] = [
  { name: 'home' }, { name: 'new' }, { name: 'project', id: 'abc123', phase: null }, { name: 'project', id: 'abc123', phase: 'requirements' },
  { name: 'project', id: 'a-b_c', phase: 'build' },
]

describe('router', () => {
  it.each(ROUTES)('every route builds a hash that parses back to itself: %j', (route) => {
    expect(parseHash(buildHash(route))).toEqual(route)
  })
  it('the empty hash and a bare slash are home', () => {
    expect(parseHash('')).toEqual({ name: 'home' })
    expect(parseHash('#')).toEqual({ name: 'home' })
    expect(parseHash('#/')).toEqual({ name: 'home' })
  })
  it('a trailing slash and a query string are ignored', () => {
    expect(parseHash('#/new/')).toEqual({ name: 'new' })
    expect(parseHash('#/projects/abc?x=1')).toEqual({ name: 'project', id: 'abc', phase: null })
  })
  it.each(['#/nonsense', '#/projects', '#/projects/a/b', '#/projects/a/phases', '#/projects/a/phases/Bad Key', '#/projects/../etc', '#/projects/%00',
    '#/projects/%E0%A4%A', '#/projects/' + 'x'.repeat(65), '#/projects/a/phases/b/extra', '#/new/extra'])('an unknown or malformed hash falls back to not-found: %s', (hash) => {
    expect(parseHash(hash).name).toBe('not-found')
  })
  it('an id that needs escaping is rejected rather than trusted', () => {
    expect(parseHash('#/projects/a%2Fb').name).toBe('not-found')
    expect(parseHash('#/projects/a%20b').name).toBe('not-found')
  })
  it('not-found builds a hash that goes home, so a bad link can always be left', () => {
    expect(buildHash({ name: 'not-found', hash: 'x' })).toBe('#/')
  })
})
