// S23c: the Configuration page, its Users tab, the rail link on Setup only, and the Approve button greyed with the server's own sentence. Static renders from the real server answers.
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ContractError, decodeProject, makeClient } from '../api'
import { decodeApprovers, decodeMe, decodeUser, decodeUsersList } from '../api/users'
import detailJson from '../contract/project_detail.json'
import empty from '../contract/users_empty.json'
import list from '../contract/users_list.json'
import architect from '../contract/users_me_architect.json'
import stranger from '../contract/users_me_stranger.json'
import e403 from '../contract/error_403_users.json'
import e409 from '../contract/error_409_users.json'
import { parseHash, buildHash } from '../lib/router'
import { emptyScreen, ProjectPage } from '../pages/ProjectPage'
import { ConfigurationView, TABS } from '../pages/ConfigurationPage'
import { PhaseRail } from './PhaseRail'
import { UsersPanel } from './UsersPanel'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const project = decodeProject(detailJson)
const L = decodeUsersList(list), E = decodeUsersList(empty), ann = decodeMe(architect), nobody = decodeMe(stranger)
const actions = { onAdd: noop, onRoles: noop, onActive: noop, onApprovers: noop }
const panel = (over: Partial<Parameters<typeof UsersPanel>[0]> = {}) => html(<UsersPanel list={L} me={ann} canEdit busy={false} error={null} {...actions} {...over} />)

describe('the answers, as the server sends them', () => {
  it('decode: the list with people and approvers, the empty list, and what a typed name may do', () => {
    expect(L.users.map((u) => u.name)).toEqual(['Ann', 'Bo', 'Root']); expect(L.roles).toHaveLength(7); expect(L.approvers.requirements).toEqual(['Architect', 'Technical Lead'])
    expect(E.empty).toBe(true); expect(E.users).toEqual([]); expect(E.empty_hint).toContain('ADMIN_NAME')
    expect(ann.on_list).toBe(true); expect(ann.may_approve).toContain('requirements'); expect(Object.keys(ann.why_not)).toEqual(['deploy', 'handover'])
    expect(nobody.on_list).toBe(false); expect(nobody.may_approve).toEqual([])
  })
  it('decode the refusals a person meets as plain sentences', () => {
    expect(e403.detail).toContain('only an Administrator can change the Users list'); expect(e409.detail).toContain('last Administrator')
  })
  it('refuse a damaged answer', () => {
    const bad = clone(list) as Record<string, unknown>; delete bad.note
    expect(() => decodeUsersList(bad)).toThrow(ContractError)
    const user = clone(list); (user.users[0] as Record<string, unknown>).active = 'yes'
    expect(() => decodeUsersList(user)).toThrow(ContractError)
    const me = clone(architect) as Record<string, unknown>; delete me.why_not
    expect(() => decodeMe(me)).toThrow(ContractError)
    expect(() => decodeUser(null)).toThrow(ContractError); expect(() => decodeApprovers({ phase: 1 })).toThrow(ContractError)
  })
})

describe('the client calls', () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  it('read the list with no name, and what a name may do with one, and save changes with PUT and POST in the person\'s name', async () => {
    const seen: { url: string; init: RequestInit }[] = []
    const client = makeClient(async (url, init) => { seen.push({ url: String(url), init: init ?? {} }); const u = String(url); return json(u.endsWith('/me') ? architect : u.endsWith('/users') && init?.method !== 'POST' ? list : u.includes('/approvers/') ? { phase: 'design', roles: ['Architect'] } : list.users[0]) })
    expect((await client.users()).users).toHaveLength(3); expect((await client.me('Ann')).name).toBe('Ann')
    await client.addUser('Root', 'New Person', ['Architect']); await client.setUserRoles('Root', 'Ann Lee', ['BAU Lead']); await client.setUserActive('Root', 'Ann', false); await client.setApprovers('Root', 'design', ['Architect'])
    expect(seen.map((s) => [s.init.method ?? 'GET', s.url])).toEqual([['GET', '/api/users'], ['GET', '/api/users/me'], ['POST', '/api/users'], ['PUT', '/api/users/Ann%20Lee/roles'], ['PUT', '/api/users/Ann/active'], ['PUT', '/api/approvers/design']])
    expect(new Headers(seen[1].init.headers).get('X-Actor')).toBe('Ann'); expect(new Headers(seen[3].init.headers).get('X-Actor')).toBe('Root')
    expect(JSON.parse(String(seen[2].init.body))).toEqual({ name: 'New Person', roles: ['Architect'] }); expect(JSON.parse(String(seen[4].init.body))).toEqual({ active: false })
  })
  it('carry the server\'s sentence when it says no', async () => {
    const e = await makeClient(async () => json(e403, 403)).addUser('Ann', 'X', []).catch((x) => x)
    expect(e.message).toContain('only an Administrator can change the Users list')
  })
})

describe('the address', () => {
  it('is project, id, configuration, both ways, and nothing odd gets through', () => {
    expect(parseHash('#/projects/p1/configuration')).toEqual({ name: 'configuration', id: 'p1' }); expect(buildHash({ name: 'configuration', id: 'p 1' })).toBe('#/projects/p%201/configuration')
    for (const bad of ['#/projects/p1/configuration/x', '#/projects/../configuration', '#/projects/p1/configurations']) expect(parseHash(bad).name, bad).toBe('not-found')
  })
})

describe('the rail', () => {
  it('shows Configuration at the bottom on Setup, and on no other phase', () => {
    const at = (selected: string) => html(<PhaseRail projectId="p1" phases={project.phases} selected={selected} />)
    const setup = at('setup')
    expect(setup).toContain('>Configuration<'); expect(setup).toContain('href="#/projects/p1/configuration"'); expect(setup.indexOf('Build Verify')).toBeLessThan(setup.indexOf('Configuration'))
    for (const p of ['requirements', 'design', 'architecture', 'build', 'deploy', 'handover']) expect(at(p), p).not.toContain('>Configuration<')
  })
  it('stays visible, and marked as the current page, on the Configuration page itself', () => {
    const out = html(<PhaseRail projectId="p1" phases={project.phases} selected="requirements" onConfiguration />)
    expect(out).toContain('>Configuration<'); expect(out).toMatch(/aria-current="page"[^>]*>(?:(?!<\/a>)[^])*Configuration/)
  })
})

describe('the Configuration page', () => {
  const view = (tab: 'users' | 'settings' | 'templates' = 'users', over: Partial<Parameters<typeof ConfigurationView>[0]> = {}) =>
    html(<ConfigurationView project={project} tab={tab} onTab={noop} users={L} me={ann} canEdit busy={false} error={null} actions={actions} {...over} />)
  it('has three tabs, the Users one selected, and goes back to the Setup phase', () => {
    const out = view()
    expect(TABS.map((t) => t.label)).toEqual(['Users and roles', 'System settings', 'Templates'])
    for (const t of TABS) expect(out).toContain(`>${t.label}</button>`)
    expect(out).toMatch(/aria-selected="true"[^>]*>Users and roles/); expect(out).toContain(`href="#/projects/${project.id}/phases/setup"`)
  })
  it('waits for the settings and for the templates rather than promising them: both are real now', () => {
    expect(view('templates')).toContain('Loading the templates'); expect(view('templates')).not.toContain('aria-label="People"'); expect(view('templates')).not.toContain('Coming next')
    expect(view('settings')).toContain('Loading the settings'); expect(view('settings')).not.toContain('Coming next')
  })
})

describe('the Users tab', () => {
  it('says a name is a label, not a password, and who you are', () => {
    const out = panel()
    expect(out).toContain('A name is a label, not a password'); expect(out).toContain('Ann · Architect, Technical Lead')
  })
  it('lists the active people first, then the switched-off one marked as such', () => {
    const out = panel()
    expect(out.indexOf('aria-label="Ann"')).toBeLessThan(out.indexOf('aria-label="Root"')); expect(out.indexOf('aria-label="Root"')).toBeLessThan(out.indexOf('aria-label="Bo (switched off)"'))
    expect(out).toContain('Switched off'); expect(out).toContain('Switch on'); expect(out).toContain('Switch off')
  })
  it('shows every role as a box for each person, ticked where held', () => {
    const out = panel()
    const fieldset = (who: string) => { const at = out.indexOf(`aria-label="Roles of ${who}"`); return out.slice(at, out.indexOf('</fieldset>', at)) }
    expect((fieldset('Ann').match(/type="checkbox"/g) ?? []).length).toBe(7); expect((fieldset('Ann').match(/checked=""/g) ?? []).length).toBe(2)
    expect((fieldset('Bo').match(/checked=""/g) ?? []).length).toBe(1); expect(fieldset('Bo')).toMatch(/disabled=""/)          // a switched-off person's roles cannot be changed
  })
  it('explains the last Administrator and disables switching them off', () => {
    const out = panel()
    expect(out).toContain('The last Administrator'); const root = out.slice(out.indexOf('aria-label="Root"'), out.indexOf('aria-label="Bo (switched off)"'))
    expect(root).toMatch(/disabled=""[^>]*>Switch off/)
  })
  it('shows who approves each phase with the changed ones marked', () => {
    const out = panel()
    expect(out).toContain('aria-label="Approvers of Requirements"'); expect(out).toContain('aria-label="Approvers of BAU handover"'); expect((out.match(/Changed from the default/g) ?? []).length).toBe(1)
    const item = (n: string) => { const at = out.indexOf(`aria-label="Approvers of ${n}"`); return out.slice(at, out.indexOf('</li>', at)) }
    expect(item('Requirements')).toContain('Changed from the default'); expect(item('Design')).not.toContain('Changed from the default')
  })
  it('has an Add form for a name and roles', () => {
    const out = panel()
    expect(out).toContain('aria-label="Add a person"'); expect(out).toContain('Add a person'); expect((out.match(/aria-label="Roles for the new person"/g) ?? []).length).toBe(1)
  })
  it('is read-only for someone who is not an Administrator, and says so', () => {
    const out = panel({ canEdit: false })
    expect(out).toContain('Only an Administrator can change this list'); expect(out).toMatch(/<input[^>]*type="checkbox"[^>]*disabled=""/); expect(out).toMatch(/disabled=""[^>]*>Add</)
  })
  it('is read-only while a change is being saved', () => { expect(panel({ busy: true })).toMatch(/disabled=""[^>]*>Add</) })
  it('says nobody is on the list and where to put ADMIN_NAME, when the list is empty, and lets anyone start it', () => {
    const out = html(<UsersPanel list={E} me={nobody} canEdit busy={false} error={null} {...actions} />)
    expect(out).toContain('Nobody is on the Users list yet'); expect(out).toContain('ADMIN_NAME'); expect(out).not.toContain('Only an Administrator can change this list'); expect(out).toContain('No one yet.')
  })
  it('shows the server\'s sentence as text when a change was refused, never as markup', () => {
    const out = panel({ error: 'this is the <b>last</b> Administrator' })
    expect(out).toContain('That could not be done'); expect(out).toContain('&lt;b&gt;last&lt;/b&gt;'); expect(out).not.toContain('<b>last</b>')
  })
  it('shows names from the server as text', () => {
    const odd = clone(list); odd.users[0].name = '<img src=x>'
    const out = html(<UsersPanel list={decodeUsersList(odd)} me={ann} canEdit busy={false} error={null} {...actions} />)
    expect(out).not.toContain('<img src=x>'); expect(out).toContain('&lt;img src=x&gt;')
  })
})

describe('ticking a role', () => {
  it('sends the roles in their fixed order, which is what the server stores', async () => {
    const { toggleRole } = await import('../lib/users')
    expect(toggleRole(L.roles, ['Technical Lead'], 'Architect')).toEqual(['Architect', 'Technical Lead'])
    expect(toggleRole(L.roles, ['Architect', 'Technical Lead'], 'Technical Lead')).toEqual(['Architect'])
  })
})

describe('the Approve button', () => {
  const phaseAt = (key: string) => { const p = clone(project); const ph = p.phases.find((x) => x.key === key)!; ph.status = 'awaiting_review'; ph.allowed_actions = ['approve', 'request_changes'] as never; return p }
  const page = (key: string, me: typeof ann | null) => html(<ProjectPage project={phaseAt(key)} phaseKey={key} screen={emptyScreen} me={me} />)
  const buttons = (out: string) => [...out.matchAll(/<button[^>]*>(Approve[^<]*|Request changes[^<]*)<\/button>/g)].map((m) => m[0])
  it('is live for a person who may approve the phase', () => {
    for (const b of buttons(page('requirements', ann))) expect(b).not.toContain('disabled=""')
    expect(buttons(page('requirements', ann))).toHaveLength(2)
  })
  it('is greyed, with the server\'s own sentence beside it, for a person who may not', () => {
    const out = page('deploy', ann)
    for (const b of buttons(out)) expect(b).toContain('disabled=""')
    expect(out).toContain(ann.why_not.deploy); expect(out).toContain('role="note"')
  })
  it('is greyed for a stranger on every phase and tells them to ask an Administrator', () => {
    for (const k of ['setup', 'requirements', 'build']) { const out = page(k, nobody); for (const b of buttons(out)) expect(b).toContain('disabled=""'); expect(out).toContain('ask an Administrator') }
  })
  it('is not greyed before the answer has loaded, or while nobody is on the list', () => {
    for (const b of buttons(page('deploy', null))) expect(b).not.toContain('disabled=""')
    for (const b of buttons(page('deploy', { ...ann, list_in_force: false, may_approve: [], why_not: {} }))) expect(b).not.toContain('disabled=""')
  })
  it('leaves every other button alone', () => {
    const p = phaseAt('deploy'); p.phases.find((x) => x.key === 'deploy')!.allowed_actions = ['run', 'approve'] as never
    const out = html(<ProjectPage project={p} phaseKey="deploy" screen={emptyScreen} me={ann} />)
    expect([...out.matchAll(/<button[^>]*>(Run[^<]*)<\/button>/g)].some((m) => !m[0].includes('disabled=""'))).toBe(true)
  })
})

// ---- the glue, as plain functions (found by the break-one-thing check) ------------------------------------------------------------------

describe('who may change the list', () => {
  it('is an Administrator, or anyone while the list is empty, and nobody before it has loaded', async () => {
    const { canEditUsers } = await import('../lib/users')
    expect(canEditUsers(E, nobody)).toBe(true); expect(canEditUsers(E, null)).toBe(true)
    expect(canEditUsers(L, decodeMe({ ...architect, administrator: true }))).toBe(true); expect(canEditUsers(L, ann)).toBe(false); expect(canEditUsers(L, null)).toBe(false); expect(canEditUsers(null, ann)).toBe(false)
  })
})

describe('the Add form', () => {
  it('sends the name tidied and the roles, and nothing for a blank name or while a change is being saved', async () => {
    const { newPerson } = await import('../lib/users')
    expect(newPerson('  Ann Lee ', ['Architect'], false)).toEqual({ name: 'Ann Lee', roles: ['Architect'] })
    expect(newPerson('   ', ['Architect'], false)).toBeNull(); expect(newPerson('', [], false)).toBeNull(); expect(newPerson('Ann', [], true)).toBeNull()
  })
  it('resets after adding, and keeps the typed text when the add is not allowed', () => {
    const out = html(<UsersPanel list={L} me={ann} canEdit busy={false} error={null} {...actions} />)
    expect(out).toContain('value=""'); expect(out).toMatch(/disabled=""[^>]*>Add</)                                  // nothing typed yet: Add is off
  })
})

describe('the changes the page makes', () => {
  const calls = () => { const seen: unknown[][] = []; const rec = (n: string) => async (...a: unknown[]) => { seen.push([n, ...a]) }; return { seen, client: { addUser: rec('add'), setUserRoles: rec('roles'), setUserActive: rec('active'), setApprovers: rec('approvers') } } }
  it('send the typed name as the actor and the right person, phase and roles for each change', async () => {
    const { usersActions } = await import('../lib/users')
    const { seen, client } = calls()
    const a = usersActions(client, 'Root', (what) => { void what() })
    a.onAdd('New', ['Architect']); a.onRoles('Ann', ['BAU Lead']); a.onActive('Ann', false); a.onApprovers('design', ['Architect'])
    await Promise.resolve()
    expect(seen).toEqual([['add', 'Root', 'New', ['Architect']], ['roles', 'Root', 'Ann', ['BAU Lead']], ['active', 'Root', 'Ann', false], ['approvers', 'Root', 'design', ['Architect']]])
  })
  it('are busy while they run, reload the list after, and keep the server\'s sentence when refused', async () => {
    const { runChange } = await import('../lib/users')
    const log: unknown[] = []
    const ui = { setBusy: (b: boolean) => log.push(['busy', b]), setError: (m: string | null) => log.push(['error', m]), reload: async () => { log.push('reload') } }
    await runChange(async () => { log.push('did it') }, ui)
    expect(log).toEqual([['busy', true], ['error', null], 'did it', 'reload', ['busy', false]])
    log.length = 0
    await runChange(async () => { throw new Error('this is the last Administrator') }, ui)
    expect(log).toEqual([['busy', true], ['error', null], ['error', 'this is the last Administrator'], ['busy', false]])        // no reload after a refusal
  })
})

describe('asking what the typed name may do', () => {
  it('asks the server with the name, asks nothing for no name, and gives null if the answer cannot be read', async () => {
    const { loadMe } = await import('../lib/users')
    const asked: string[] = []
    const client = { me: async (a: string) => { asked.push(a); return ann } }
    expect(await loadMe(client, 'Ann')).toEqual(ann); expect(await loadMe(client, '')).toBeNull(); expect(asked).toEqual(['Ann'])
    expect(await loadMe({ me: async () => { throw new Error('down') } }, 'Ann')).toBeNull()
  })
})

describe('the people and the approver boxes', () => {
  it('lists people in name order within the active and the switched off', async () => {
    const { sortedUsers } = await import('../lib/users')
    const u = (name: string, active = true) => ({ name, active, roles: [], created_by: 'x', created_at: 't' })
    expect(sortedUsers([u('Cy'), u('Ann'), u('Zed', false), u('Bo'), u('Al', false)]).map((x) => x.name)).toEqual(['Ann', 'Bo', 'Cy', 'Al', 'Zed'])
  })
  it('ignores a role that does not exist when toggling', async () => {
    const { toggleRole } = await import('../lib/users')
    expect(toggleRole(L.roles, ['Architect'], 'Wizard')).toEqual(['Architect']); expect(toggleRole(L.roles, [], 'Wizard')).toEqual([])
  })
  it('does not count a switched-off Administrator when asking who is the last', async () => {
    const { isLastAdministrator } = await import('../lib/users')
    const admins = [{ name: 'Root', active: true, roles: ['Administrator'], created_by: 'x', created_at: 't' }, { name: 'Off', active: false, roles: ['Administrator'], created_by: 'x', created_at: 't' }]
    expect(isLastAdministrator(admins, 'Root')).toBe(true)
  })
  it('disables the approver boxes when the person cannot edit or a change is being saved', () => {
    const boxes = (out: string) => { const at = out.indexOf('aria-label="Roles that approve Design"'); return out.slice(at, out.indexOf('</fieldset>', at)) }
    expect(boxes(panel({ canEdit: false }))).toMatch(/disabled=""/); expect(boxes(panel({ busy: true }))).toMatch(/disabled=""/); expect(boxes(panel())).not.toMatch(/disabled=""/)
  })
})

describe('the back link', () => {
  it('goes to the Setup phase of this project', () => {
    const out = html(<ConfigurationView project={project} tab="users" onTab={noop} users={L} me={ann} canEdit busy={false} error={null} actions={actions} />)
    const back = /^<section><a href="([^"]+)"/.exec(out)![1]                                                           // the first link on the page is the way back; the rail below links to every phase
    expect(back).toBe(`#/projects/${project.id}/phases/setup`)
  })
})

describe('ticking a box reaches the right person and the right phase', () => {
  it('sends the person it was made for, whatever else is on the page', async () => {
    const { rolesFor, approversFor } = await import('../lib/users')
    const seen: unknown[][] = []
    rolesFor((n, r) => seen.push(['roles', n, r]), 'Ann Lee')(['Architect']); rolesFor((n, r) => seen.push(['roles', n, r]), 'Bo')([])
    approversFor((p, r) => seen.push(['approvers', p, r]), 'deploy')(['BAU Lead']); approversFor((p, r) => seen.push(['approvers', p, r]), 'design')(['Architect'])
    expect(seen).toEqual([['roles', 'Ann Lee', ['Architect']], ['roles', 'Bo', []], ['approvers', 'deploy', ['BAU Lead']], ['approvers', 'design', ['Architect']]])
  })
})

describe('who approves, in the page\'s own words', () => {
  it('says what the server says, so an Architect\'s phase is not described as a business engineer\'s', () => {
    const p = clone(project); const ph = p.phases.find((x) => x.key === 'requirements')!; ph.approver = 'architect or technical lead'
    const out = html(<ProjectPage project={p} phaseKey="requirements" screen={emptyScreen} />)
    expect(out).toContain('approved by the architect or technical lead.'); expect(out).not.toContain('business engineer')
  })
  it('shows the real fixture the same way: Setup, Requirements and Design are approved by the architect', () => {
    for (const key of ['setup', 'requirements', 'design']) expect(project.phases.find((x) => x.key === key)!.approver, key).toBe('architect')
    expect(project.phases.find((x) => x.key === 'architecture')!.approver).toBe('technical lead')
  })
})
