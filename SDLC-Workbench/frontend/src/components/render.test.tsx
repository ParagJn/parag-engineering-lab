// Components are checked by rendering to static HTML (no browser, no DOM library). What is asserted is what a person would see
// and what the server's words turn into: text, never markup.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { BackendUnreachable, decodeCatalogue, decodePlan, decodeProject, decodeProjectList, type PhaseDetail, type ProjectDetail } from '../api'
import catalogueJson from '../contract/catalogue.json'
import detailJson from '../contract/project_detail.json'
import listJson from '../contract/projects_list.json'
import planJson from '../contract/plan_preview.json'
import { initialWizard, type WizardState } from '../lib/wizard'
import { HomePage } from '../pages/HomePage'
import { ProjectPage } from '../pages/ProjectPage'
import { WizardPage, type WizardProps } from '../pages/WizardPage'
import { ModeChip, SimulatedBadge, StatusPill } from './Badges'
import { NamePrompt } from './NamePrompt'
import { Notice, Spinner } from './Notice'
import { PhaseRail } from './PhaseRail'
import { Shell } from './Shell'

const html = (node: React.ReactElement) => renderToStaticMarkup(node)
const catalogue = decodeCatalogue(catalogueJson)
const plan = decodePlan(planJson)
const detail = decodeProject(detailJson)
const projects = decodeProjectList(listJson)
const noop = () => {}
// A button that is really disabled has the attribute disabled="" -- the Tailwind class "disabled:opacity-40" is on every button and proves nothing.
const disabledButton = (label: string) => new RegExp(`<button[^>]*\\sdisabled=""[^>]*>${label}`)

describe('the shell', () => {
  it('shows a REPLAY chip and the name', () => {
    const out = html(<Shell mode="replay" actorName="Parag" onChangeName={noop}><p>body</p></Shell>)
    expect(out).toContain('REPLAY')
    expect(out).not.toContain('LIVE')
    expect(out).toContain('Parag')
    expect(out).toContain('body')
  })
  it('shows a LIVE chip', () => {
    const out = html(<Shell mode="live" actorName="Parag" onChangeName={noop}>x</Shell>)
    expect(out).toContain('LIVE')
    expect(out).not.toContain('REPLAY')
  })
  it('says the mode is unknown rather than guessing, and "not set" without a name', () => {
    const out = html(<Shell mode={null} actorName="" onChangeName={noop}>x</Shell>)
    expect(out).toContain('mode unknown')
    expect(out).not.toMatch(/REPLAY|LIVE/)
    expect(out).toContain('not set')
  })
  it('offers a way to change the name', () => {
    expect(html(<Shell mode="replay" actorName="P" onChangeName={noop}>x</Shell>)).toContain('Change your name')
  })
})

describe('messages', () => {
  it('the unreachable sentence is shown as text with an alert role', () => {
    const out = html(<Notice tone="error" title="The backend is not reachable">{new BackendUnreachable().message}</Notice>)
    expect(out).toContain('role="alert"')
    expect(out).toContain('./start.sh')
  })
  it('a server sentence containing markup is escaped, never interpreted', () => {
    const out = html(<Notice tone="error">{'<img src=x onerror=alert(1)> <script>bad()</script>'}</Notice>)
    expect(out).not.toMatch(/<img|<script/i)
    expect(out).toContain('&lt;img')
  })
  it('info and warn are polite status regions, not alerts', () => {
    expect(html(<Notice tone="info">a</Notice>)).toContain('role="status"')
    expect(html(<Notice tone="warn">a</Notice>)).not.toContain('role="alert"')
  })
  it('loading shows its label', () => {
    expect(html(<Spinner label="Loading projects" />)).toContain('Loading projects')
  })
})

describe('badges', () => {
  it('the simulated badge says Simulated', () => {
    expect(html(<SimulatedBadge />)).toMatch(/Simulated/)
  })
  it('chips and pills carry their own words', () => {
    expect(html(<ModeChip mode="live" />)).toContain('LIVE')
    expect(html(<StatusPill status="awaiting_review" />)).toContain('Awaiting review')
    expect(html(<StatusPill status="rejected" />)).toContain('Sent back')
  })
})

describe('the name prompt', () => {
  it('says it is a label, not a sign-in, and disables Continue while blank', () => {
    const out = html(<NamePrompt initial="" onSave={noop} />)
    expect(out).toContain('not a sign-in')
    expect(out).toMatch(disabledButton('Continue'))
    expect(out).not.toContain('Cancel')
  })
  it('enables Continue for a valid name and offers Cancel when it can be cancelled', () => {
    const out = html(<NamePrompt initial="Parag" onSave={noop} onCancel={noop} />)
    expect(out).not.toMatch(disabledButton('Continue'))
    expect(out).toContain('Cancel')
    expect(out).not.toContain('role="alert"')
  })
  it('shows the reason for a name that is not allowed', () => {
    const out = html(<NamePrompt initial="system" onSave={noop} />)
    expect(out).toContain('role="alert"')
    expect(out).toMatch(disabledButton('Continue'))
  })
})

describe('the project list', () => {
  it('the empty state offers a way forward', () => {
    const out = html(<HomePage projects={[]} />)
    expect(out).toContain('No projects yet.')
    expect(out).toContain('href="#/new"')
  })
  it('the sample project is offered whether or not there are projects already', () => {
    expect(html(<HomePage projects={[]} />)).toContain('href="#/new/sample"')
    expect(html(<HomePage projects={projects} />)).toContain('href="#/new/sample"')
    expect(html(<HomePage projects={projects} />)).toContain('Load the sample project')
  })
  it('lists each project as a link with its name, mode and progress', () => {
    expect(projects.length).toBeGreaterThan(0)    // precondition: the fixture has a project
    const out = html(<HomePage projects={projects} />)
    expect(out).not.toContain('No projects yet.')
    for (const p of projects) {
      expect(out).toContain(`href="#/projects/${encodeURIComponent(p.id)}"`)
      expect(out).toContain(p.name)
      expect(out).toContain(`${p.phases_approved} of`)
    }
  })
  it('a project name with markup is shown as text', () => {
    const evil = { ...projects[0], name: '<script>x()</script>' }
    const out = html(<HomePage projects={[evil]} />)
    expect(out).not.toContain('<script>')
    expect(out).toContain('&lt;script&gt;')
  })
})

describe('the phase rail', () => {
  it('lists the phases in order, marks the selected one, and links by project and phase', () => {
    const out = html(<PhaseRail projectId={detail.id} phases={detail.phases} selected="requirements" />)
    const names = detail.phases.map((p) => p.name)
    const positions = names.map((n) => out.indexOf(`>${n.replace(/&/g, '&amp;')}<`))
    expect(positions.every((i) => i >= 0)).toBe(true)
    expect([...positions].sort((a, b) => a - b)).toEqual(positions)
    expect(out.match(/aria-current="page"/g)).toHaveLength(1)
    expect(out).toContain(`href="#/projects/${encodeURIComponent(detail.id)}/phases/requirements"`)
  })
  it('flags a phase that needs review', () => {
    const phases: PhaseDetail[] = detail.phases.map((p) => (p.key === 'setup' ? { ...p, needs_review: true } : p))
    expect(html(<PhaseRail projectId="p" phases={phases} selected="setup" />)).toContain('review')
  })
})

describe('the project page', () => {
  it('opens on the first phase that is not approved and has artefacts, and shows the server\'s next action', () => {
    const out = html(<ProjectPage project={detail} phaseKey={null} />)
    expect(out).toContain(detail.name)
    expect(out).toContain(detail.next_action)
    expect(out).toContain('Setup')
  })
  it('a blocked phase says what it waits for', () => {
    const blocked = detail.phases.find((p) => p.blocked_by && p.status === 'not_started')
    expect(blocked).toBeTruthy()      // precondition
    const out = html(<ProjectPage project={detail} phaseKey={blocked!.key} />)
    expect(out).toContain(`Waiting for ${blocked!.blocked_by} to be approved first.`)
    expect(out).toContain('Nothing to do here right now.')
  })
  it('shows the actions the server allows, as working buttons (S12b)', () => {
    const open = detail.phases.find((p) => p.allowed_actions.includes('run'))
    expect(open).toBeTruthy()
    const out = html(<ProjectPage project={detail} phaseKey={open!.key} />)
    expect(out).toContain('Run this phase')
    expect(out).not.toMatch(disabledButton('Run this phase'))
  })
  it('shows no action the server did not allow', () => {
    const blocked = detail.phases.find((p) => p.allowed_actions.length === 0)!
    const out = html(<ProjectPage project={detail} phaseKey={blocked.key} />)
    expect(out).not.toMatch(/Run this phase|Approve|Request changes|Hand to review/)
  })
  it('noted connectors are labelled simulated', () => {
    const withConnectors: ProjectDetail = { ...detail, connectors: ['ci_cd', 'source_control'] }
    const out = html(<ProjectPage project={withConnectors} phaseKey={null} />)
    expect(out).toContain('CI/CD')
    expect(out).toContain('Source control')
    expect(out).toMatch(/Simulated/)
  })
  it('no connectors means no connectors line and no badge', () => {
    const out = html(<ProjectPage project={{ ...detail, connectors: [] }} phaseKey={null} />)
    expect(out).not.toContain('Connectors noted')
    expect(out).not.toMatch(/Simulated/)
  })
  it('feedback a reviewer sent back is shown as text', () => {
    const phases = detail.phases.map((p, i) => (i === 0 ? { ...p, feedback: '<b onmouseover=x>redo</b>' } : p))
    const out = html(<ProjectPage project={{ ...detail, phases }} phaseKey={detail.phases[0].key} />)
    expect(out).toContain('Sent back')
    expect(out).not.toContain('<b onmouseover')
    expect(out).toContain('&lt;b onmouseover')
  })
  it('an unknown phase key falls back to a real phase instead of crashing', () => {
    expect(() => html(<ProjectPage project={detail} phaseKey="no_such_phase" />)).not.toThrow()
  })
})

describe('the wizard page', () => {
  const props = (state: WizardState, extra: Partial<WizardProps> = {}): WizardProps => ({
    state, catalogue, modeInfo: { mode: 'replay', meaning: 'This server answers from recordings.', reviews_available: false }, plan, planError: null, submitError: null,
    submitting: false, onChange: noop, onToggleArtefact: noop, onToggleConnector: noop, onBack: noop, onNext: noop, onCreate: noop, ...extra,
  })
  const at = (step: WizardState['step'], patch: Partial<WizardState> = {}): WizardState => ({ ...initialWizard(catalogue), name: 'Rooms', step, ...patch })

  it('basics: a blank name shows the problem and disables Next and Back', () => {
    const out = html(<WizardPage {...props({ ...initialWizard(catalogue) })} />)
    expect(out).toContain('Give the project a name.')
    expect(out).toMatch(disabledButton('Next'))
    expect(out).toMatch(disabledButton('Back'))
  })
  it('basics: with a name Next is enabled and there is no problem', () => {
    const out = html(<WizardPage {...props(at('basics'))} />)
    expect(out).not.toMatch(disabledButton('Next'))
    expect(out).not.toContain('role="alert"')
  })
  it('the stepper marks the current step', () => {
    expect(html(<WizardPage {...props(at('produce'))} />)).toMatch(/aria-current="step"[^>]*>(<svg.*?<\/svg>)?3 What to produce/)
  })
  it('mode: states the server\'s mode as a fact with no switch', () => {
    const out = html(<WizardPage {...props(at('mode'))} />)
    expect(out).toContain('This server is in REPLAY mode.')
    expect(out).toContain('answers from recordings')
    expect(out).not.toContain('type="radio"')
  })
  it('produce: required artefacts are ticked and disabled, optional ones can be changed', () => {
    const out = html(<WizardPage {...props(at('produce'))} />)
    const boxes = [...out.matchAll(/<input type="checkbox"([^>]*)>/g)].map((m) => m[1])
    expect(boxes.length).toBe(catalogue.phases.flatMap((p) => p.artefacts).length)
    expect(boxes.some((b) => b.includes('disabled'))).toBe(true)
    expect(boxes.some((b) => !b.includes('disabled'))).toBe(true)
    expect(out).toContain('(required)')
  })
  it('produce: an unticked optional artefact renders unchecked', () => {
    const phase = catalogue.phases.find((p) => p.artefacts.some((a) => !a.required))!
    const key = phase.artefacts.find((a) => !a.required)!.key
    const state = at('produce')
    state.ticked = { ...state.ticked, [phase.key]: state.ticked[phase.key].filter((k) => k !== key) }
    const withOut = [...html(<WizardPage {...props(state)} />).matchAll(/<input type="checkbox"([^>]*)>/g)].filter((m) => !m[1].includes('checked')).length
    const all = [...html(<WizardPage {...props(at('produce'))} />).matchAll(/<input type="checkbox"([^>]*)>/g)].filter((m) => !m[1].includes('checked')).length
    expect(withOut).toBe(all + 1)
  })
  it('produce: the server\'s notes and a plan error are shown and a plan error blocks Next', () => {
    const withNotes = html(<WizardPage {...props(at('produce'), { plan: { ...plan, notes: ['Epics is included because it is needed.'] } })} />)
    expect(withNotes).toContain('Epics is included because it is needed.')
    const bad = html(<WizardPage {...props(at('produce'), { planError: 'Personas is required and cannot be switched off.' })} />)
    expect(bad).toContain('Personas is required and cannot be switched off.')
    expect(bad).toMatch(disabledButton('Next'))
  })
  it('context: for a plain project it does not claim a sample document is included', () => {
    const out = html(<WizardPage {...props(at('context'))} />)
    expect(out).not.toContain('will be added for you')
    expect(out).toContain('you can add or remove more on the project page')
  })
  it('context: offers choosing files and pasting text, and says they are added when the project is created', () => {
    const out = html(<WizardPage {...props(at('context'))} />)
    expect(out).toContain('Choose files')
    expect(out).toContain('type="file"')
    expect(out).toContain('multiple')
    expect(out).toContain('Paste text')
    expect(out).toContain('<textarea')
    expect(out).toContain('added when the project is created')
    expect(out).not.toContain('Documents to add')      // nothing staged yet
  })
  it('context: staged documents are listed with a way to take each one back out', () => {
    const staged = [{ key: 'a', filename: 'policy.md', size: 2048, blob: new Blob(['x']) }, { key: 'b', filename: '<b>x</b>.txt', size: 10, blob: new Blob(['x']) }]
    const out = html(<WizardPage {...props(at('context', { documents: staged }))} />)
    expect(out).toContain('aria-label="Documents to add"')
    expect(out).toContain('policy.md')
    expect(out).toContain('2.0 KB')
    expect(out).toContain('aria-label="Do not add policy.md"')
    expect(out).not.toContain('<b>x</b>')
    expect(out).toContain('&lt;b&gt;x&lt;/b&gt;.txt')
  })
  it('context: a file that could not be staged is explained', () => {
    const out = html(<WizardPage {...props(at('context'), { documentProblem: '“a.exe” is not a supported file type; use .txt, .md.' })} />)
    expect(out).toContain('That file was not added')
    expect(out).toContain('a.exe')
  })
  it('review: lists every document that will be added, the sample\'s and the person\'s', () => {
    const staged = [{ key: 'a', filename: 'extra.md', size: 5, blob: new Blob(['x']) }]
    const out = html(<WizardPage {...props(at('review', { documents: staged }), { sample: { filename: 'meeting-room-policy.md' } })} />)
    expect(out).toContain('2 documents will be added: meeting-room-policy.md, extra.md.')
    expect(html(<WizardPage {...props(at('review'))} />)).not.toContain('will be added')
  })
  it('context: the sample project says its policy note goes in too', () => {
    const out = html(<WizardPage {...props(at('context'), { sample: { filename: 'meeting-room-policy.md' } })} />)
    expect(out).toContain('meeting-room-policy.md will be added for you when the project is created.')
  })
  it('connectors: all four are badged simulated and the notice says nothing is connected', () => {
    const out = html(<WizardPage {...props(at('connectors'))} />)
    for (const label of ['Source control', 'Issue tracker', 'CI/CD', 'Cloud account']) expect(out).toContain(label)
    expect(out.match(/Simulated/g)?.length).toBe(4)
    expect(out).toContain('Nothing is connected')
  })
  it('connectors: a ticked one renders checked', () => {
    const out = html(<WizardPage {...props(at('connectors', { connectors: ['ci_cd'] }))} />)
    expect(out.match(/<input type="checkbox" checked=""/g)).toHaveLength(1)
  })
  it('review: shows the choices, offers Create, and shows the server\'s refusal as text', () => {
    const out = html(<WizardPage {...props(at('review', { brief: 'Staff book rooms.', connectors: ['ci_cd'] }), { submitError: '<i>name taken</i>' })} />)
    expect(out).toContain('Rooms')
    expect(out).toContain('Staff book rooms.')
    expect(out).toContain('Simulated connectors noted: CI/CD')
    expect(out).toContain('Create project')
    expect(out).not.toMatch(/>Next</)
    expect(out).toContain('&lt;i&gt;name taken')
    expect(out).not.toContain('<i>name taken')
  })
  it('review: Create is disabled while submitting, which also says so', () => {
    const out = html(<WizardPage {...props(at('review'), { submitting: true })} />)
    expect(out).toMatch(disabledButton('Creating…'))
  })
})
