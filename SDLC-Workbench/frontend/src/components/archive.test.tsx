// Archiving a project (S12b addendum 1): the card, the confirm, the archived list and the read-only banner, rendered to static HTML.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeProject, decodeProjectList } from '../api'
import detailJson from '../contract/project_detail.json'
import listJson from '../contract/projects_list.json'
import { HomePage } from '../pages/HomePage'
import { ProjectCard } from './ProjectCard'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const [active] = decodeProjectList(listJson)
const archived = { ...active, name: 'Old one', archived_at: '2026-01-02T00:00:00.000Z' }
const disabledButton = (label: string) => new RegExp(`<button[^>]*\\sdisabled=""[^>]*>(<svg[^>]*>.*?</svg> )?${label}`)
const base = { confirming: false, busy: false, canChange: true, onAskArchive: noop, onCancel: noop, onArchive: noop, onRestore: noop }
const buttons = (out: string) => [...out.matchAll(/<button[^>]*>(?:<svg[^>]*>.*?<\/svg> )?([^<]*)<\/button>/g)].map((m) => m[1].trim())

describe('the decoders carry archived_at', () => {
  it('an active project has none, and the field is required (a missing one is a contract problem)', () => {
    expect(active.archived_at).toBeNull()
    const bad = JSON.parse(JSON.stringify(listJson)); delete bad.projects[0].archived_at
    expect(() => decodeProjectList(bad)).toThrow(/archived_at/)
  })
  it('the detail has it too', () => {
    expect(decodeProject(detailJson).archived_at).toBeNull()
    const bad = JSON.parse(JSON.stringify(detailJson)); delete bad.archived_at
    expect(() => decodeProject(bad)).toThrow(/archived_at/)
  })
  it('a date decodes, and a number does not', () => {
    const ok = JSON.parse(JSON.stringify(listJson)); ok.projects[0].archived_at = '2026-01-02T00:00:00.000Z'
    expect(decodeProjectList(ok)[0].archived_at).toBe('2026-01-02T00:00:00.000Z')
    ok.projects[0].archived_at = 5
    expect(() => decodeProjectList(ok)).toThrow()
  })
})

describe('the project card', () => {
  it('an active project offers Archive, and not Restore', () => {
    const out = html(<ProjectCard project={active} {...base} />)
    expect(buttons(out)).toEqual(['Archive'])
    expect(out).toContain(`aria-label="Archive ${active.name}"`)
    expect(out).not.toContain('Archived')
  })
  it('the name is the link; the card itself is not one (a button cannot sit inside a link)', () => {
    const out = html(<ProjectCard project={active} {...base} />)
    expect(out).toContain(`<a href="#/projects/${active.id}"`)
    expect(out.indexOf('<button')).toBeGreaterThan(out.lastIndexOf('</a>'))
  })
  it('pressing Archive shows the confirm, which names the project and says nothing is lost', () => {
    const out = html(<ProjectCard project={active} {...base} confirming />)
    expect(out).toContain('role="alertdialog"')
    expect(out).toContain(`Archive “${active.name}”?`)
    expect(out).toContain('documents and artefacts are kept')
    expect(out).toContain('Show archived')
    expect(buttons(out)).toEqual(['Archive', 'Cancel'])      // the card's own Archive button is hidden while asking
  })
  it('busy turns the confirm buttons off and says what it is doing', () => {
    const out = html(<ProjectCard project={active} {...base} confirming busy />)
    expect(out).toMatch(disabledButton('Archiving…'))
    expect(out).toMatch(disabledButton('Cancel'))
  })
  it('without a name the buttons are off', () => {
    expect(html(<ProjectCard project={active} {...base} canChange={false} />)).toMatch(disabledButton('Archive'))
    expect(html(<ProjectCard project={archived} {...base} canChange={false} />)).toMatch(disabledButton('Restore'))
  })
  it('an archived project says so, shows when, and offers Restore only', () => {
    const out = html(<ProjectCard project={archived} {...base} />)
    expect(out).toContain('Archived')
    expect(out).toContain('archived 2 Jan 2026')
    expect(buttons(out)).toEqual(['Restore'])
    expect(out).toContain('aria-label="Restore Old one"')
  })
  it('an archived project never shows the confirm, even if one was pending', () => {
    expect(html(<ProjectCard project={archived} {...base} confirming />)).not.toContain('alertdialog')
  })
  it('an archived project does not show a live status pill', () => {
    const live = { ...archived, active_phase: { key: 'setup', name: 'Setup', status: 'running' as const } }
    expect(html(<ProjectCard project={live} {...base} />)).not.toContain('>Running<')
  })
  it('a name with markup is text', () => {
    const out = html(<ProjectCard project={{ ...active, name: '<img src=x onerror=1>' }} {...base} confirming />)
    expect(out).not.toMatch(/<img/)
    expect(out).toContain('&lt;img')
  })
})

describe('the home page', () => {
  it('asks which project is being confirmed and no other', () => {
    const second = { ...active, id: 'p2', name: 'Second' }
    const out = html(<HomePage projects={[active, second]} confirming="p2" />)
    expect(out.match(/role="alertdialog"/g)).toHaveLength(1)
    expect(out).toContain('Archive “Second”?')
  })
  it('the archived view has its own title, empty state and a ticked switch', () => {
    const empty = html(<HomePage projects={[]} showArchived />)
    expect(empty).toContain('Archived projects')
    expect(empty).toContain('Nothing is archived.')
    expect(empty).not.toContain('No projects yet.')
    expect(empty).toMatch(/<input type="checkbox" checked=""/)
    expect(html(<HomePage projects={[]} />)).not.toMatch(/<input type="checkbox" checked=""/)
  })
  it('the archived view lists archived projects with Restore', () => {
    const out = html(<HomePage projects={[archived]} showArchived />)
    expect(out).toContain('Old one')
    expect(buttons(out)).toContain('Restore')
    expect(buttons(out)).not.toContain('Archive')
  })
  it('a refusal from the server is shown as text', () => {
    const out = html(<HomePage projects={[active]} error="<b>Setup</b> is being written right now" />)
    expect(out).toContain('&lt;b&gt;Setup')
    expect(out).toContain('role="alert"')
  })
  it('the switch is there on a non-empty active list too', () => {
    expect(html(<HomePage projects={[active]} />)).toContain('Show archived')
  })
})
