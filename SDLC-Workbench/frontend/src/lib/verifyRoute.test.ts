import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { PhaseRail } from '../components/PhaseRail'
import { buildHash, parseHash } from './router'
import detailJson from '../contract/project_detail.json'
import { decodeProject } from '../api'

describe('the Build Verify address', () => {
  it('goes to the project\'s own verify page and back', () => {
    expect(buildHash({ name: 'verify', id: 'p1' })).toBe('#/projects/p1/verify')
    expect(parseHash('#/projects/p1/verify')).toEqual({ name: 'verify', id: 'p1' })
    expect(parseHash('#/projects/p1/verify/')).toEqual({ name: 'verify', id: 'p1' })
    expect(parseHash('#/projects/a_b-1/verify')).toEqual({ name: 'verify', id: 'a_b-1' }); expect(parseHash('#/projects/a%20b/verify').name).toBe('not-found')           // an ID is letters, digits, _ and -
  })
  it('writes the address of an ID with a special character the way the browser needs it', () => {
    expect(buildHash({ name: 'verify', id: 'a_b-1' })).toBe('#/projects/a_b-1/verify')
    expect(buildHash({ name: 'verify', id: 'a b' })).toBe('#/projects/a%20b/verify'); expect(buildHash({ name: 'verify', id: 'a/b' })).toBe('#/projects/a%2Fb/verify')
  })
  it('refuses a page it does not have', () => {
    for (const bad of ['#/projects/p1/verify/1', '#/projects/p1/verifyx', '#/projects/../verify', '#/projects/p1/Verify', '#/verify']) expect(parseHash(bad).name).toBe('not-found')
  })
})

describe('the link in the rail', () => {
  const phases = decodeProject(detailJson).phases
  const html = (verify: boolean) => renderToStaticMarkup(createElement(PhaseRail, { projectId: 'p1', phases, selected: 'setup', onVerify: verify }))
  it('sits beside Traceability and is marked as the current page only on its own page', () => {
    expect(html(false)).toContain('href="#/projects/p1/verify"'); expect(html(false)).toContain('Build Verify')
    expect(html(true)).toMatch(/href="#\/projects\/p1\/verify" aria-current="page"/); expect(html(false)).not.toMatch(/href="#\/projects\/p1\/verify" aria-current/)
  })
})
