// Artefacts that are part of the design but not in use (S21a): decoded, kept out of the wizard's ticks, listed with their reason, and drawn as a grey card.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ContractError, decodeCatalogue, decodePlan, decodeProject } from '../api'
import catalogueJson from '../contract/catalogue.json'
import planJson from '../contract/plan_preview.json'
import detailJson from '../contract/project_detail.json'
import { initialWizard, selectionOf, toggleArtefact } from '../lib/wizard'
import { emptyScreen, ProjectPage } from '../pages/ProjectPage'
import { WizardPage, type WizardProps } from '../pages/WizardPage'
import { ByHandCard, NotEnabledCard } from './ArtefactCard'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const catalogue = decodeCatalogue(catalogueJson)
const OFF = ['infrastructure_as_code', 'cicd_pipeline']
const HANDOVER_OFF = ['support_guide', 'slos_alerts', 'kt_pack']           // S22b: the three parked Handover artefacts
const noop = () => {}
const wizardProps = (state: ReturnType<typeof initialWizard>): WizardProps => ({
  state, catalogue, modeInfo: { mode: 'replay', meaning: 'This server answers from recordings.', reviews_available: false }, plan: decodePlan(planJson), planError: null, submitError: null,
  submitting: false, onChange: noop, onToggleArtefact: noop, onToggleConnector: noop, onBack: noop, onNext: noop, onCreate: noop,
})

describe('the catalogue and the plan, as the server sends them', () => {
  it('says which artefacts are not enabled, with the server\'s reason, and everything else is enabled with no reason', () => {
    const all = catalogue.phases.flatMap((p) => p.artefacts)
    expect(all.filter((a) => !a.enabled).map((a) => a.key)).toEqual([...OFF, ...HANDOVER_OFF])
    expect(all.filter((a) => !a.enabled).every((a) => a.disabled_reason.startsWith('Not enabled.') && !a.required)).toBe(true)
    expect(all.filter((a) => a.enabled).every((a) => a.disabled_reason === '')).toBe(true)
  })
  it('lists in the plan only what will run, and apart from it what is not enabled', () => {
    const deploy = decodePlan(planJson).phases.find((p) => p.key === 'deploy')!
    expect(deploy.artefacts.map((a) => a.key)).toEqual(['deployment_plan', 'release_notes']); expect(deploy.by_hand.map((b) => b.key)).toEqual(['deployment_verification'])
    expect(deploy.not_enabled.map((n) => n.key)).toEqual(OFF); expect(deploy.not_enabled.every((n) => n.reason.length > 20)).toBe(true)
    expect(decodePlan(planJson).phases.filter((p) => p.key !== 'deploy' && p.key !== 'handover').every((p) => p.not_enabled.length === 0)).toBe(true)
    const handover = decodePlan(planJson).phases.find((p) => p.key === 'handover')!         // S22b
    expect(handover.artefacts.map((a) => a.key)).toEqual(['runbook', 'hypercare_plan']); expect(handover.by_hand.map((b) => b.key)).toEqual(['handover_signoff']); expect(handover.not_enabled.map((n) => n.key)).toEqual(HANDOVER_OFF)
  })
  it('lists on each phase of a project the artefacts that are not enabled', () => {
    const phases = decodeProject(detailJson).phases
    expect(phases.find((p) => p.key === 'deploy')!.not_enabled.map((n) => n.key)).toEqual(OFF)
    expect(phases.find((p) => p.key === 'deploy')!.artefacts.map((a) => a.key)).toEqual(['deployment_plan', 'release_notes'])
    expect(phases.find((p) => p.key === 'deploy')!.by_hand.map((b) => b.key)).toEqual(['deployment_verification'])
    expect(phases.filter((p) => p.key !== 'deploy' && p.key !== 'handover').every((p) => p.not_enabled.length === 0)).toBe(true)
    expect(phases.find((p) => p.key === 'handover')!.not_enabled.map((n) => n.key)).toEqual(HANDOVER_OFF)
    expect(phases.find((p) => p.key === 'handover')!.by_hand.map((b) => b.key)).toEqual(['handover_signoff'])
  })
  it('refuses an answer where the fields are missing or the wrong type', () => {
    const noFlag = clone(catalogueJson); delete (noFlag.phases[0].artefacts[0] as Record<string, unknown>).enabled
    expect(() => decodeCatalogue(noFlag)).toThrow(ContractError)
    const noReason = clone(catalogueJson); delete (noReason.phases[0].artefacts[0] as Record<string, unknown>).disabled_reason
    expect(() => decodeCatalogue(noReason)).toThrow(ContractError)
    const badPlan = clone(planJson); (badPlan.phases[5] as Record<string, unknown>).not_enabled = [{ key: 'x', name: 'X' }]
    expect(() => decodePlan(badPlan)).toThrow(ContractError)
    const noList = clone(detailJson); delete (noList.phases[0] as Record<string, unknown>).not_enabled
    expect(() => decodeProject(noList)).toThrow(ContractError)
  })
})

describe('the wizard page and an artefact that is not enabled', () => {
  it('lists each one under its phase with the reason in words, and gives it no checkbox', () => {
    const state = { ...initialWizard(catalogue), name: 'Rooms', step: 'produce' as const }
    const out = html(<WizardPage {...wizardProps(state)} />)
    expect(out).toContain('aria-label="Not enabled in Deploy"'); expect(out).toContain('aria-label="Not enabled in BAU handover"')
    for (const key of [...OFF, ...HANDOVER_OFF]) {
      const a = catalogue.phases.flatMap((p) => p.artefacts).find((x) => x.key === key)!
      expect(out).toContain(`<span class="font-semibold">${a.name}</span>: ${a.disabled_reason}`)
    }
    expect(out.match(/aria-label="Not enabled in /g)).toHaveLength(2)                       // only the two phases that have any
    const labels = [...out.matchAll(/<label[^>]*>(?:(?!<\/label>)[^])*<\/label>/g)].map((m) => m[0])
    expect(labels.some((l) => l.includes('Infrastructure as code') || l.includes('CI/CD pipeline'))).toBe(false)         // no checkbox label for either
    expect(labels.some((l) => l.includes('Deployment plan'))).toBe(true)
  })
})

describe('the wizard and an artefact that is not enabled', () => {
  it('never ticks it, never asks for it, and ignores a press on it', () => {
    const state = initialWizard(catalogue)
    for (const key of OFF) expect(state.ticked.deploy).not.toContain(key)
    expect(state.ticked.deploy).toEqual(['deployment_plan', 'release_notes'])          // the verification is done by hand, so it is not something to tick
    expect(selectionOf(state, catalogue)).toEqual({})                                          // nothing was unticked, so the selection is "everything"
    for (const key of [...OFF, 'deployment_verification']) expect(toggleArtefact(state, catalogue, 'deploy', key)).toBe(state)
  })
  it('still sends a selection when a person unticks something that can be unticked', () => {
    const state = initialWizard(catalogue)
    const optional = catalogue.phases.find((p) => p.key === 'requirements')!.artefacts.find((a) => !a.required)!
    const next = toggleArtefact(state, catalogue, 'requirements', optional.key)
    const sel = selectionOf(next, catalogue)
    expect(Object.keys(sel)).toEqual(['requirements']); expect(sel.requirements).not.toContain(optional.key)
    expect(Object.keys(sel).includes('deploy')).toBe(false)
  })
})

describe('the grey card', () => {
  it('names the artefact, says Not enabled and gives the reason, as text, with nothing to press', () => {
    const out = html(<NotEnabledCard name="CI/CD pipeline" reason="Not enabled. No automated build or release is wanted yet." />)
    expect(out).toContain('aria-label="CI/CD pipeline: not enabled"'); expect(out).toContain('>Not enabled</span>'); expect(out).toContain('No automated build or release is wanted yet.')
    expect(out).not.toContain('<button'); expect(out).not.toContain('<a '); expect(out).not.toContain('role="button"'); expect(out).not.toContain('tabindex')
  })
  it('shows a reason from the server as text, never as markup', () => {
    const out = html(<NotEnabledCard name="<b>x</b>" reason="<script>alert(1)</script>" />)
    expect(out).not.toContain('<script>'); expect(out).not.toContain('<b>x</b>'); expect(out).toContain('&lt;script&gt;')
  })
})

describe('the Deploy page', () => {
  const project = decodeProject(detailJson)
  const page = (key: string) => html(<ProjectPage project={project} phaseKey={key} />)
  it('shows the three artefacts that run, then two grey cards with their reasons, and counts them apart', () => {
    const out = page('deploy')
    for (const name of ['Deployment plan', 'Release notes', 'Deployment verification']) expect(out).toContain(name)
    expect(out).toContain('aria-label="Deployment verification: done by hand"'); expect(out).toContain('Use the checklist below; no model is involved.')
    expect(out).toContain('aria-label="Infrastructure as code: not enabled"'); expect(out).toContain('aria-label="CI/CD pipeline: not enabled"')
    expect(out).toContain('2 artefacts'); expect(out).toContain('1 done by hand'); expect(out).toContain('2 not enabled')
    expect(out).toContain('The product is built and run outside this tool'); expect(out).toContain('No automated build or release is wanted yet')
    expect(out.indexOf('Release notes')).toBeLessThan(out.indexOf('Deployment verification')); expect(out.indexOf('Deployment verification')).toBeLessThan(out.indexOf('Infrastructure as code'))      // written, then by hand, then switched off
  })
  it('shows no grey card and no "not enabled" count on any other phase', () => {
    for (const p of project.phases.filter((x) => x.key !== 'deploy' && x.key !== 'handover')) {
      const out = page(p.key)
      expect(out).not.toContain(': not enabled"'); expect(out).not.toContain(' not enabled')
    }
  })
  it('shows the Handover page the same way: two documents, the sign-off by hand, then three grey cards, counted apart', () => {          // S22b
    const out = page('handover')
    for (const name of ['Runbook', 'Hypercare plan', 'Handover sign-off']) expect(out).toContain(name)
    expect(out).toContain('aria-label="Handover sign-off: done by hand"')
    for (const name of ['Support guide', 'SLOs and alerts', 'Knowledge-transfer pack']) expect(out).toContain(`aria-label="${name}: not enabled"`)
    expect(out).toContain('2 artefacts'); expect(out).toContain('1 done by hand'); expect(out).toContain('3 not enabled'); expect(out).toContain('Not needed yet; the runbook covers day-to-day problems.')
    expect(out.indexOf('Hypercare plan')).toBeLessThan(out.indexOf('Handover sign-off')); expect(out.indexOf('Handover sign-off')).toBeLessThan(out.indexOf('Support guide'))      // written, then by hand, then switched off
  })
})

describe('the by-hand card', () => {
  it('names the artefact, says Done by hand, points at the checklist and has nothing to press', () => {
    const out = html(<ByHandCard name="Deployment verification" description="Checks a person works through." progress="4 of 16 answered · overall: Go" />)
    expect(out).toContain('aria-label="Deployment verification: done by hand"'); expect(out).toContain('>Done by hand</span>'); expect(out).toContain('Use the checklist below; no model is involved.')
    expect(out).toContain('4 of 16 answered · overall: Go'); expect(out).not.toContain('<button'); expect(out).not.toContain('<a ')
  })
  it('shows no progress until it is known, and never says it failed or was not written', () => {
    const out = html(<ByHandCard name="Deployment verification" description="d" />)
    expect(out).not.toContain('answered'); for (const word of ['Failed', 'failed', 'not written yet', 'no skill']) expect(out).not.toContain(word)
  })
  it('shows a description from the server as text, never as markup', () => {
    const out = html(<ByHandCard name="<b>x</b>" description="<script>alert(1)</script>" />)
    expect(out).not.toContain('<script>'); expect(out).not.toContain('<b>x</b>'); expect(out).toContain('&lt;script&gt;')
  })
  it('shows on the Deploy page with the checklist\'s progress when it has loaded, and on no other phase', async () => {
    const { decodeChecklist } = await import('../api')
    const answered = (await import('../contract/checklist_answered.json')).default
    const project = decodeProject(detailJson)
    const withList = html(<ProjectPage project={project} phaseKey="deploy" screen={{ ...emptyScreen, checklist: decodeChecklist(answered) }} />)
    expect(withList).toContain('4 of 16 answered · overall: Go')
    expect(html(<ProjectPage project={project} phaseKey="deploy" screen={emptyScreen} />)).toContain('Done by hand')
    for (const p of project.phases.filter((x) => x.key !== 'deploy' && x.key !== 'handover')) expect(html(<ProjectPage project={project} phaseKey={p.key} screen={emptyScreen} />)).not.toContain('Done by hand')
  })
  it('is listed in the wizard under its phase and given no checkbox', () => {
    const state = { ...initialWizard(catalogue), name: 'Rooms', step: 'produce' as const }
    const out = html(<WizardPage {...wizardProps(state)} />)
    expect(out).toContain('aria-label="Done by hand in Deploy"'); expect(out).toContain('you work through it by hand.')
    const labels = [...out.matchAll(/<label[^>]*>(?:(?!<\/label>)[^])*<\/label>/g)].map((m) => m[0])
    expect(labels.some((l) => l.includes('Deployment verification'))).toBe(false)
  })
  it('is decoded from the catalogue as by hand, and nothing else is', () => {
    const all = catalogue.phases.flatMap((p) => p.artefacts)
    expect(all.filter((a) => a.by_hand).map((a) => a.key)).toEqual(['deployment_verification', 'handover_signoff'])
    const noFlag = clone(catalogueJson); delete (noFlag.phases[0].artefacts[0] as Record<string, unknown>).by_hand
    expect(() => decodeCatalogue(noFlag)).toThrow(ContractError)
  })
})

describe('the by-hand card, the last edges', () => {
  it('has no role and no tab stop, so it cannot be pressed or reached like a button', () => {
    const out = html(<ByHandCard name="Deployment verification" description="d" progress="p" />)
    expect(out).not.toContain('role="button"'); expect(out).not.toContain('tabindex'); expect(out).not.toContain('onclick'); expect(out.match(/<li/g)).toHaveLength(1)
  })
  it('shows the checklist\'s progress on the page, as the card\'s own words, when the checklist has loaded', async () => {
    const { decodeChecklist } = await import('../api')
    const answered = (await import('../contract/checklist_answered.json')).default
    const blank = (await import('../contract/checklist_empty.json')).default
    const project = decodeProject(detailJson)
    const card = (c: unknown) => { const out = html(<ProjectPage project={project} phaseKey="deploy" screen={{ ...emptyScreen, checklist: decodeChecklist(c) }} />); return out.slice(out.indexOf('aria-label="Deployment verification: done by hand"'), out.indexOf('</li>', out.indexOf('aria-label="Deployment verification: done by hand"'))) }
    expect(card(answered)).toContain('4 of 16 answered · overall: Go'); expect(card(blank)).toContain('0 of 16 answered · no overall decision yet')
  })
})

