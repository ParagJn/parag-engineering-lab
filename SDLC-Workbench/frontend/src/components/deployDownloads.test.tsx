// Downloading the deployment plan and the release notes as Markdown and Word (S21b): where the links are, what they point at, and where they are not.
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeArtefactDetail } from '../api'
import artefactDetailJson from '../contract/artefact_detail.json'
import { applyEvent, idle, type Progress } from '../state/runProgress'
import { DOWNLOADABLE_TYPES, downloadPath, isDownloadable } from '../lib/format'
import { ArtefactReader } from './ArtefactReader'
import { RunPanel } from './RunPanel'
import { decodeProject } from '../api'
import projectJson from '../contract/project_detail.json'
import { emptyScreen, ProjectPage } from '../pages/ProjectPage'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const detail = (over: Record<string, unknown> = {}) => decodeArtefactDetail({ ...(artefactDetailJson as object), ...over })
const NONE = Symbol('no project')
const read = (over: Record<string, unknown>, project: string | typeof NONE = 'p1') => html(<ArtefactReader artefact={detail(over)} projectId={project === NONE ? undefined : project} onClose={noop} onVersion={noop} />)

describe('the address of a download', () => {
  it('names the project, the artefact, the format and, when given, the version', () => {
    expect(downloadPath('p1', 'DEP-PLN-001', 'md')).toBe('/api/projects/p1/artefacts/DEP-PLN-001/download?format=md')
    expect(downloadPath('p1', 'DEP-PLN-001', 'docx', 3)).toBe('/api/projects/p1/artefacts/DEP-PLN-001/download?format=docx&version=3')
    expect(downloadPath('p1', 'A', 'md', null)).not.toContain('version'); expect(downloadPath('p1', 'A', 'md', 0)).not.toContain('version')
  })
  it('keeps an ID with odd characters inside its place in the address', () => {
    expect(downloadPath('a/b?c', 'x y#z', 'md')).toBe('/api/projects/a%2Fb%3Fc/artefacts/x%20y%23z/download?format=md')
  })
  it('is offered for the four documents an agent writes in the last two phases, and nothing else', () => {
    expect([...DOWNLOADABLE_TYPES]).toEqual(['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'])
    for (const yes of ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan']) expect(isDownloadable(yes), yes).toBe(true)
    for (const other of ['deployment_verification', 'handover_signoff', 'support_guide', 'slos_alerts', 'kt_pack', 'personas', 'build_instructions', 'infrastructure_as_code', '', 'deployment_plans', 'runbooks']) expect(isDownloadable(other), other).toBe(false)
  })
})

describe('the artefact page', () => {
  it('offers .md and .docx for the version on show, as ordinary links that download', () => {
    const out = read({ type: 'deployment_plan', id: 'DEP-PLN-001', version: 2 })
    expect(out).toContain('Version 2:'); expect(out).toContain('Download .md'); expect(out).toContain('Download .docx')
    expect(out).toContain('href="/api/projects/p1/artefacts/DEP-PLN-001/download?format=md&amp;version=2"'); expect(out).toContain('href="/api/projects/p1/artefacts/DEP-PLN-001/download?format=docx&amp;version=2"')
    expect((out.match(/ download=""/g) ?? []).length).toBe(2); expect(out).toContain('aria-label="Download this version"')
  })
  it('follows the version being read, so an older version downloads as that older version', () => {
    expect(read({ type: 'release_notes', id: 'DEP-REL-001', version: 1, latest_version: 3, is_latest: false })).toContain('version=1')
  })
  it('is there for the release notes too, and absent for every other artefact', () => {
    expect(read({ type: 'release_notes', id: 'DEP-REL-001' })).toContain('Download .docx')
    for (const type of ['personas', 'build_instructions', 'deployment_verification', 'low_level_design']) {
      const out = read({ type })
      expect(out).not.toContain('Download .md'); expect(out).not.toContain('Download .docx')
    }
  })
  it('is absent when the page does not know its project', () => { expect(read({ type: 'deployment_plan' }, NONE)).not.toContain('Download .docx') })
})

const e = (id: number, type: string, data: Record<string, unknown>) => ({ id, type, run_id: 'r', at: 't', ...data }) as never
/** Events are numbered in order here (the run drops an event it has already seen), whatever ids the pieces were written with. */
const progress = (events: unknown[]): Progress => (events as Record<string, unknown>[]).map((ev, n) => ({ ...ev, id: n + 1 }) as never).reduce((p: Progress, ev) => applyEvent(p, ev), idle)
const finished = (key: string, id: string, version = 2) => [e(1, 'artefact.started', { key }), e(2, 'artefact.finished', { key, artefact_id: id, version, attempts: 1, cost_usd: 0.02, items: 3, flags: 0, author: 'agent:x@m' })]
const start = e(1, 'run.started', { phase: 'deploy', artefacts: ['deployment_plan', 'release_notes', 'personas'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 })
const panel = (p: Progress, project: string | typeof NONE = 'p1') => html(
  <RunPanel progress={p} names={{ deployment_plan: 'Deployment plan', release_notes: 'Release notes', personas: 'Personas' }} connected cancelling={false} cancelNote={null} problem={null} onCancel={noop} onOpen={noop} projectId={project === NONE ? undefined : project} />)

describe('the run panel', () => {
  it('puts a Markdown and a Word link beside Read it for a written plan, for the version it wrote', () => {
    const out = panel(progress([start, ...finished('deployment_plan', 'DEP-PLN-001', 4)]))
    expect(out).toContain('href="/api/projects/p1/artefacts/DEP-PLN-001/download?format=md&amp;version=4"'); expect(out).toContain('href="/api/projects/p1/artefacts/DEP-PLN-001/download?format=docx&amp;version=4"')
    expect(out).toContain('aria-label="Download Deployment plan as Markdown"'); expect(out).toContain('aria-label="Download Deployment plan as Word"')
    expect(out.indexOf('format=md')).toBeLessThan(out.indexOf('Read it'))
  })
  it('does the same for the release notes and for nothing else', () => {
    const out = panel(progress([start, ...finished('release_notes', 'DEP-REL-001', 1).map((x) => x), ]))
    expect(out).toContain('DEP-REL-001/download?format=docx')
    const other = panel(progress([start, ...finished('personas', 'REQ-PER-001')]))
    expect(other).toContain('Read it'); expect(other).not.toContain('download?format')
  })
  it('has no such links while the artefact is still being written, or when it failed, or when the project is not known', () => {
    expect(panel(progress([start, e(1, 'artefact.started', { key: 'deployment_plan' })]))).not.toContain('download?format')
    expect(panel(progress([start, e(1, 'artefact.started', { key: 'deployment_plan' }), e(2, 'artefact.failed', { key: 'deployment_plan', reason: 'no' })]))).not.toContain('download?format')
    expect(panel(progress([start, ...finished('deployment_plan', 'DEP-PLN-001')]), NONE)).not.toContain('download?format')
  })
  it('keeps Read it at the right edge when there is nothing to download beside it', () => {
    expect(panel(progress([start, ...finished('personas', 'REQ-PER-001')]))).toContain('ml-auto text-xs underline">Read it')
  })
})

describe('the project page passes the project to both places', () => {
  const project = decodeProject(projectJson)
  const open = (type: string, id: string) => decodeArtefactDetail({ ...(artefactDetailJson as object), type, id, version: 3, latest_version: 3, is_latest: true })
  it('so the open plan or notes show their download links', () => {
    const out = html(<ProjectPage project={project} phaseKey="deploy" screen={{ ...emptyScreen, open: open('deployment_plan', 'DEP-PLN-001') }} />)
    expect(out).toContain(`href="/api/projects/${project.id}/artefacts/DEP-PLN-001/download?format=docx&amp;version=3"`)
  })
  it('and the run panel of the phase being run shows its links', () => {
    const run = progress([e(1, 'run.started', { phase: 'deploy', artefacts: ['deployment_plan'], concurrency: 3, review: false, max_cost_usd: 5, max_seconds: 1800 }),
      e(2, 'artefact.started', { key: 'deployment_plan' }), e(3, 'artefact.finished', { key: 'deployment_plan', artefact_id: 'DEP-PLN-001', version: 1, attempts: 1, cost_usd: 0.01, items: 1, flags: 0, author: 'agent:x@m' })])
    const out = html(<ProjectPage project={project} phaseKey="deploy" screen={{ ...emptyScreen, progress: run }} />)
    expect(out).toContain(`/api/projects/${project.id}/artefacts/DEP-PLN-001/download?format=md&amp;version=1`)
  })
})

