// The contract: every fixture the backend wrote must be accepted by the decoders the screen uses. If a field is renamed or retyped
// on the server, `export_contract` rewrites the fixture and THIS file fails here; if it is renamed here, it fails on the server's test.
import { describe, expect, it } from 'vitest'
import { ContractError, decodeCatalogue, decodeError, decodeMode, decodePlan, decodeProject, decodeProjectList, decodeStatus } from '../api'
import catalogue from './catalogue.json'
import error400 from './error_400.json'
import error404 from './error_404.json'
import error422 from './error_422.json'
import modes from './modes.json'
import planPreview from './plan_preview.json'
import projectCreated from './project_created.json'
import projectDetail from './project_detail.json'
import projectsEmpty from './projects_empty.json'
import projectsList from './projects_list.json'
import status from './status.json'

describe('the backend fixtures decode', () => {
  it('catalogue: 7 phases and 33 artefacts', () => {
    const c = decodeCatalogue(catalogue)
    expect(c.phases).toHaveLength(7)
    expect(c.phases.flatMap((p) => p.artefacts)).toHaveLength(33)
    expect(c.phases[0].key).toBe('setup')
  })

  it('plan preview: the waves and the wave of each artefact agree', () => {
    const plan = decodePlan(planPreview)
    const reqs = plan.phases.find((p) => p.key === 'requirements')!
    expect(reqs.artefacts.map((a) => a.key)).not.toContain('user_stories')
    for (const phase of plan.phases) {
      for (const a of phase.artefacts) expect(phase.waves[a.wave - 1]).toContain(a.key)
    }
  })

  it('mode: replay with a sentence', () => {
    const m = decodeMode(modes)
    expect(m.mode).toBe('replay')
    expect(m.meaning.length).toBeGreaterThan(10)
  })

  it('projects: an empty list and a list with one project', () => {
    expect(decodeProjectList(projectsEmpty)).toEqual([])
    const [p] = decodeProjectList(projectsList)
    expect(p.name).toBe('Meeting Room Booking')
    expect(p.phases_total).toBe(7)
    expect(p.active_phase).toBeNull()
  })

  it('a created project and a read project are the same shape and say connectors are simulated', () => {
    for (const body of [projectCreated, projectDetail]) {
      const p = decodeProject(body)
      expect(p.phases.map((x) => x.key)).toEqual(['setup', 'requirements', 'design', 'architecture', 'build', 'deploy', 'handover'])
      expect(p.connectors).toEqual(['source_control', 'ci_cd'])
      expect(p.connectors_are_simulated).toBe(true)
    }
  })

  it('allowed actions come from the server: only Setup is startable on a new project', () => {
    const p = decodeProject(projectDetail)
    expect(p.phases.find((x) => x.key === 'setup')!.allowed_actions).toEqual(['run'])
    for (const phase of p.phases.filter((x) => x.key !== 'setup')) {
      expect(phase.allowed_actions).toEqual([])
      expect(phase.blocked_by).toBe('Setup')
    }
  })

  it('the status summary needs only the mode and the database line', () => {
    const s = decodeStatus(status)
    expect(['replay', 'live']).toContain(s.mode)
    expect(s.schema_version).toBeGreaterThanOrEqual(5)
  })

  it('error bodies carry a sentence in "detail"', () => {
    expect(decodeError(error400)).toMatch(/needs a name/)
    expect(decodeError(error404)).toMatch(/not found/)
    expect(decodeError(error422)).toMatch(/required and cannot be switched off/)
  })
})

describe('the decoders refuse a response that does not match', () => {
  it('a missing field is a contract problem, named, not a crash later', () => {
    const broken = { ...(projectDetail as Record<string, unknown>) }
    delete broken.phases
    expect(() => decodeProject(broken)).toThrow(ContractError)
    expect(() => decodeProject(broken)).toThrow(/project\.phases/)
  })

  it('a renamed field is caught', () => {
    const renamed = { ...(projectDetail as Record<string, unknown>), name: undefined, title: 'x' }
    expect(() => decodeProject(renamed)).toThrow(/project\.name/)
  })

  it('an unknown status or action is refused rather than rendered', () => {
    const detail = JSON.parse(JSON.stringify(projectDetail))
    detail.phases[0].status = 'exploded'
    expect(() => decodeProject(detail)).toThrow(/unexpected value "exploded"/)
    const detail2 = JSON.parse(JSON.stringify(projectDetail))
    detail2.phases[0].allowed_actions = ['launch_missiles']
    expect(() => decodeProject(detail2)).toThrow(/launch_missiles/)
  })

  it('a wrong type is refused', () => {
    const detail = JSON.parse(JSON.stringify(projectDetail))
    detail.phases[0].order = '1'
    expect(() => decodeProject(detail)).toThrow(/expected a number/)
    expect(() => decodeProjectList({ projects: 'none' })).toThrow(/expected a list/)
    expect(() => decodeProject(null)).toThrow(/expected an object/)
    expect(() => decodeProject([])).toThrow(/expected an object/)
  })

  it('the server\'s own validation errors are shown in its words', () => {
    expect(decodeError({ detail: [{ msg: 'String should have at least 1 character' }, { msg: 'Field required' }] })).toBe('String should have at least 1 character; Field required')
    expect(() => decodeError({ detail: 5 })).toThrow(ContractError)
    expect(() => decodeError({})).toThrow(ContractError)
  })
})
