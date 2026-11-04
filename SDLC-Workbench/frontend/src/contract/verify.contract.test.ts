// Build Verify's answers (S20), decoded from what the real server returned. If a route's shape changes, this fails until the screen is changed to match.
import { describe, expect, it } from 'vitest'
import { ContractError, decodeError, decodeVerifyDetail, decodeVerifyList, decodeVerifyMatch, decodeVerifyRun } from '../api'
import run from './verify_run.json'
import list from './verify_list.json'
import error422 from './error_422_verify.json'
import error404 from './error_404_verify.json'

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))

describe('a check, as the server answers it', () => {
  const detail = decodeVerifyDetail(run)
  it('names the run, the person, the folders as typed and the design versions it compared against', () => {
    expect(detail).toMatchObject({ id: 1, by: 'human:Demo Person', backend_path: '/projects/build/backend', frontend_path: '/projects/build/frontend' })
    expect(Object.keys(detail.design).sort()).toEqual(['DES-HFS-001', 'DES-LLD-001'])
    expect(detail.advice).toBe('')                                    // the answer to a new check holds no advice; the list and a single run do, and the screen reads the list's
  })
  it('has the counts of all four areas, in the order the screen draws them', () => {
    expect(detail.counts.map((c) => c.area)).toEqual(['endpoint', 'table', 'screen', 'rule'])
    const endpoints = detail.counts[0]
    expect(endpoints.found + endpoints.differences + endpoints.possible + endpoints.not_found + endpoints.weak).toBe(endpoints.designed)
  })
  it('has a match for every designed item and one for every built thing nobody designed, each with a state the screen can draw', () => {
    expect(detail.matches.filter((m) => m.designed !== null).map((m) => m.designed)).toEqual(['API-001', 'API-002', 'API-003', 'TBL-001', 'HFS-001', 'RUL-001'])
    expect(detail.matches.filter((m) => m.state === 'extra').every((m) => m.designed === null && m.built !== '')).toBe(true)
    expect(detail.matches.find((m) => m.designed === 'RUL-001')?.state).toBe('weak')
  })
  it('says where each found thing is, by a path relative to the folder, and never an absolute path or source text', () => {
    for (const m of detail.matches) { expect(m.file.startsWith('/')).toBe(false); expect(m.file.length).toBeLessThan(400) }
    expect(JSON.stringify(run)).not.toContain('never-read'); expect(JSON.stringify(run)).not.toContain('SECRET')
  })
  it('lists what could not be read, including the file that may hold a secret', () => { expect(detail.notes).toContain('backend: left out .env (it may hold a secret)') })
})

describe('the list of runs', () => {
  it('holds the advice and runs without their matches', () => {
    const decoded = decodeVerifyList(list)
    expect(decoded.advice).toContain('highlighter'); expect(decoded.runs).toHaveLength(1); expect(decoded.runs[0].counts).toHaveLength(4)
    expect(list.runs[0]).not.toHaveProperty('matches')
  })
})

describe('what the server refuses', () => {
  it('says a bad folder in a plain sentence and an unknown run as not found', () => {
    expect(decodeError(error422)).toContain('there is no folder at'); expect(decodeError(error404)).toBe('verify run 99 not found in this project')
  })
})

describe('a damaged answer is refused, not guessed at', () => {
  it('a run missing a field, with an unknown area or state, or a count that is not a number', () => {
    const noId = clone(run) as Record<string, unknown>; delete noId.id
    expect(() => decodeVerifyDetail(noId)).toThrow(ContractError)
    const area = clone(run); area.counts[0].area = 'banana' as never
    expect(() => decodeVerifyDetail(area)).toThrow(ContractError)
    const state = clone(run); state.matches[0].state = 'great' as never
    expect(() => decodeVerifyDetail(state)).toThrow(ContractError)
    const n = clone(run); n.counts[0].found = 'many' as never
    expect(() => decodeVerifyDetail(n)).toThrow(ContractError)
    expect(() => decodeVerifyRun(null)).toThrow(ContractError); expect(() => decodeVerifyMatch([])).toThrow(ContractError); expect(() => decodeVerifyList({ runs: [] })).toThrow(ContractError)
  })
  it('a design version that is not a number, or a note that is not text', () => {
    const v = clone(run); v.design['DES-LLD-001'] = 'one' as never
    expect(() => decodeVerifyDetail(v)).toThrow(ContractError)
    const note = clone(run); note.notes = [7 as never]
    expect(() => decodeVerifyDetail(note)).toThrow(ContractError)
  })
  it('a built thing keeps no designed id, and a designed id that is a number is refused', () => {
    expect(decodeVerifyDetail(run).matches.filter((m) => m.state === 'extra').every((m) => m.designed === null)).toBe(true)
    const bad = clone(run); bad.matches[0].designed = 7 as never
    expect(() => decodeVerifyDetail(bad)).toThrow(ContractError)
  })
  it('an old answer without advice still decodes, with an empty one', () => {
    const o = clone(run) as Record<string, unknown>; delete o.advice
    expect(decodeVerifyDetail(o).advice).toBe('')
  })
})
