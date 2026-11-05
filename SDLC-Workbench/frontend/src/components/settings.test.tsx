// S23d, S23e: the System settings tab. Static renders and plain functions, from the real server answers. A secret is only ever Set or Not set.
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ContractError, decodeProject, makeClient } from '../api'
import { decodeSettings } from '../api/settings'
import viewJson from '../contract/settings_view.json'
import savedJson from '../contract/settings_saved.json'
import e403 from '../contract/error_403_settings.json'
import e422 from '../contract/error_422_settings.json'
import detailJson from '../contract/project_detail.json'
import * as L from '../lib/settings'
import { ConfigurationView } from '../pages/ConfigurationPage'
import { SettingsPanel, type SettingsPanelProps } from './SettingsPanel'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const V = decodeSettings(viewJson), SAVED = decodeSettings(savedJson)
const entries = (v: typeof V) => Object.fromEntries(v.groups.flatMap((g) => g.settings).map((s) => [s.key, s]))
const E = entries(V)
const panel = (over: Partial<SettingsPanelProps> = {}) => html(<SettingsPanel view={V} draft={{}} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} {...over} />)

describe('the answers, as the server sends them', () => {
  it('decode into twelve groups of settings, with secrets that only say whether they are set', () => {
    expect(V.groups).toHaveLength(12); expect(V.groups.flatMap((g) => g.settings)).toHaveLength(65)
    expect(E.ibm_ica_api_key.secret).toBe(true); expect(E.ibm_ica_api_key.is_set).toBe(true); expect(E.ibm_ica_api_key).not.toHaveProperty('value'); expect(E.ibm_ica_api_key).not.toHaveProperty('default')
    expect(E.run_budget_usd.secret).toBe(false); expect(E.run_budget_usd.value).toBe('5.0'); expect(E.run_budget_usd).not.toHaveProperty('is_set')
  })
  it('say what can be done and what is waiting', () => {
    expect(V.can_edit).toBe(true); expect(V.editable).toBe(true); expect(V.restart_pending).toBe(false); expect(V.restart_sentence).toBe('Saved. Restart the app for this to take effect.')
  })
  it('decode a save: what changed, the backup, the message, and a restart waiting', () => {
    expect(SAVED.saved).toEqual({ changed: ['IBM_ICA_API_KEY', 'RUN_BUDGET_USD'], backup: 'env-20260101-000000-000001.bak', message: 'Saved. Restart the app for this to take effect.' })
    expect(SAVED.restart_pending).toBe(true); expect(SAVED.backups).toHaveLength(1); expect(entries(SAVED).run_budget_usd.value).toBe('5.0')                 // the running app still has the old value
  })
  it('hold no secret value anywhere, in either answer', () => {
    const text = JSON.stringify(viewJson) + JSON.stringify(savedJson)
    for (const leaked of ['scratch-key', 'new-scratch-key', 'gateway.example']) expect(text).not.toContain(leaked)
  })
  it('refuse a damaged answer', () => {
    const bad = clone(viewJson) as Record<string, unknown>; delete bad.restart_sentence
    expect(() => decodeSettings(bad)).toThrow(ContractError)
    const kind = clone(viewJson); (kind.groups[0].settings[0] as Record<string, unknown>).kind = 'banana'
    expect(() => decodeSettings(kind)).toThrow()
    const secret = clone(viewJson) as { groups: { settings: Record<string, unknown>[] }[] }; const s = secret.groups.flatMap((g) => g.settings).find((x) => x.secret)!; delete s.is_set
    expect(() => decodeSettings(secret)).toThrow(ContractError)
    const plain = clone(viewJson) as { groups: { settings: Record<string, unknown>[] }[] }; const p = plain.groups.flatMap((g) => g.settings).find((x) => !x.secret)!; delete p.default
    expect(() => decodeSettings(plain)).toThrow(ContractError)
  })
  it('carry the refusals as plain sentences', () => {
    expect(e403.detail).toContain('only an Administrator'); expect(e422.detail.problems).toEqual(['RUN_BUDGET_USD: Input should be less than or equal to 1000'])
  })
})

describe('the client calls', () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  it('read with no name, save with a PUT in the person\'s name, and restore with a POST', async () => {
    const seen: { url: string; init: RequestInit }[] = []
    const client = makeClient(async (url, init) => { seen.push({ url: String(url), init: init ?? {} }); return json(init?.method === 'PUT' ? savedJson : String(url).endsWith('/restore') ? savedJson : viewJson) })
    expect((await client.settings()).groups).toHaveLength(12)
    expect((await client.saveSettings('Root', { run_budget_usd: '7.5' })).saved?.changed).toHaveLength(2)
    await client.restoreSettings('Root', 'env-20260101-000000-000001.bak')
    expect(seen.map((s) => [s.init.method ?? 'GET', s.url])).toEqual([['GET', '/api/settings'], ['PUT', '/api/settings'], ['POST', '/api/settings/restore']])
    expect(JSON.parse(String(seen[1].init.body))).toEqual({ values: { run_budget_usd: '7.5' } }); expect(JSON.parse(String(seen[2].init.body))).toEqual({ name: 'env-20260101-000000-000001.bak' })
    expect(new Headers(seen[1].init.headers).get('X-Actor')).toBe('Root'); expect(new Headers(seen[2].init.headers).get('X-Actor')).toBe('Root')
  })
  it('send the typed name when reading, so the server can say whether this person may change them', async () => {
    const seen: Headers[] = []
    const client = makeClient(async (_url, init) => { seen.push(new Headers(init?.headers)); return json(viewJson) })
    await client.settings('Parag'); await client.settings(); await client.settings('')
    expect(seen.map((h) => h.get('X-Actor'))).toEqual(['Parag', null, null])                         // with no name the read still works, and the server says nobody may edit
  })
  it('carry the server\'s refusal, with its list of problems', async () => {
    const e = await makeClient(async () => json(e422, 422)).saveSettings('Root', { run_budget_usd: '5000' }).catch((x) => x)
    expect(e.message).toContain('would not accept them'); expect(e.problems).toEqual(['RUN_BUDGET_USD: Input should be less than or equal to 1000'])
    const f = await makeClient(async () => json(e403, 403)).saveSettings('Ann', {}).catch((x) => x)
    expect(f.message).toContain('only an Administrator')
  })
})

describe('what is in the boxes', () => {
  it('starts a normal box at its value and a secret box EMPTY, so no secret is ever on the screen', () => {
    expect(L.startValue(E.run_budget_usd)).toBe('5.0'); expect(L.startValue(E.ibm_ica_api_key)).toBe('')
  })
  it('shows what was typed in place of where the box started', () => {
    expect(L.boxValue(E.run_budget_usd, {})).toBe('5.0'); expect(L.boxValue(E.run_budget_usd, { run_budget_usd: '9' })).toBe('9'); expect(L.boxValue(E.run_budget_usd, { run_budget_usd: '' })).toBe('')
  })
  it('knows a box was changed only when it differs from where it started, and a secret only once something is typed', () => {
    expect(L.isEdited(E.run_budget_usd, {})).toBe(false); expect(L.isEdited(E.run_budget_usd, { run_budget_usd: '5.0' })).toBe(false); expect(L.isEdited(E.run_budget_usd, { run_budget_usd: '6' })).toBe(true)
    expect(L.isEdited(E.run_budget_usd, { run_budget_usd: '' })).toBe(true)                                                         // emptying a normal box is a change
    expect(L.isEdited(E.ibm_ica_api_key, { ibm_ica_api_key: '' })).toBe(false); expect(L.isEdited(E.ibm_ica_api_key, { ibm_ica_api_key: '   ' })).toBe(false); expect(L.isEdited(E.ibm_ica_api_key, { ibm_ica_api_key: 'new' })).toBe(true)
  })
  it('sends only the boxes that were really changed', () => {
    const draft = { run_budget_usd: '7', app_mode: 'replay', ibm_ica_api_key: '', ibm_ica_endpoint: 'https://new', replay_set: 'demo' }
    expect(L.changes(V, draft)).toEqual({ run_budget_usd: '7', ibm_ica_endpoint: 'https://new' }); expect(L.editedCount(V, draft)).toBe(2); expect(L.changes(V, {})).toEqual({})
  })
  it('puts one box back without touching the others', () => {
    expect(L.reset({ a: '1', b: '2' }, 'a')).toEqual({ b: '2' }); expect(L.reset({}, 'a')).toEqual({})
  })
})

describe('whether Save can be pressed', () => {
  const d = { run_budget_usd: '7' }
  it('needs a change, the right to save, a settings file the app may write, and nothing already being saved', () => {
    expect(L.canSave(V, d, false)).toBe(true); expect(L.canSave(V, {}, false)).toBe(false); expect(L.canSave(V, d, true)).toBe(false)
    expect(L.canSave({ ...V, can_edit: false }, d, false)).toBe(false); expect(L.canSave({ ...V, editable: false }, d, false)).toBe(false)
  })
  it('says why not, in words', () => {
    expect(L.editNotice(V)).toBeNull(); expect(L.editNotice({ ...V, can_edit: false })).toBe('Only an Administrator can change settings. You can read them.')
    expect(L.editNotice({ ...V, editable: false })).toContain('cannot be changed here'); expect(L.editNotice({ ...V, editable: false, can_edit: false })).toContain('cannot be changed here')
  })
})

describe('the words', () => {
  it('shows a restart banner only while one is waiting', () => {
    expect(L.restartBanner(V)).toBeNull(); expect(L.restartBanner(SAVED)).toBe('Saved. Restart the app for this to take effect.')
  })
  it('says Set or Not set for a secret', () => {
    expect(L.secretWords(E.ibm_ica_api_key)).toBe('Set'); expect(L.secretWords({ ...E.ibm_ica_api_key, is_set: false })).toBe('Not set')
  })
  it('notes the default only beside a changed setting, never for a secret', () => {
    expect(L.defaultNote(E.run_budget_usd)).toBeNull(); expect(L.defaultNote({ ...E.run_budget_usd, value: '7.0', changed: true })).toBe('Default: 5.0 USD'); expect(L.defaultNote({ ...E.replay_set, changed: true, default: '' })).toBe('Default: blank')
    expect(L.defaultNote(E.ibm_ica_api_key)).toBeNull()
  })
  it('counts the changed settings of a group', () => {
    expect(L.changedIn([E.run_budget_usd, { ...E.run_max_cost_usd, changed: true }, E.ibm_ica_api_key])).toBe(1)
  })
  it('says what was saved', () => {
    expect(L.savedSentence(SAVED.saved!)).toBe('Saved. Restart the app for this to take effect. Changed: IBM_ICA_API_KEY, RUN_BUDGET_USD.')
    expect(L.savedSentence({ changed: [], backup: '', message: 'Nothing was different, so nothing was saved.' })).toBe('Nothing was different, so nothing was saved.')
  })
  it('hides what is typed into a secret box and nothing else', () => {
    expect(L.inputType(E.ibm_ica_api_key)).toBe('password'); expect(L.inputType(E.run_budget_usd)).toBe('text')
  })
})

describe('a save, step by step', () => {
  it('is busy while it runs, shows the new view and clears the draft', async () => {
    const log: unknown[] = []
    await L.runSave(async () => SAVED, { setBusy: (b) => log.push(['busy', b]), setError: (m, p) => log.push(['error', m, p]), setView: (v) => log.push(['view', v.restart_pending]), clearDraft: () => log.push('clear') })
    expect(log).toEqual([['busy', true], ['error', null, []], ['view', true], 'clear', ['busy', false]])
  })
  it('keeps what was typed and shows the server\'s sentences when refused', async () => {
    const log: unknown[] = []
    const refused = Object.assign(new Error('the settings were not saved'), { problems: ['RUN_BUDGET_USD: Input should be less than or equal to 1000'] })
    await L.runSave(async () => { throw refused }, { setBusy: (b) => log.push(['busy', b]), setError: (m, p) => log.push(['error', m, p]), setView: () => log.push('view'), clearDraft: () => log.push('clear') })
    expect(log).toEqual([['busy', true], ['error', null, []], ['error', 'the settings were not saved', ['RUN_BUDGET_USD: Input should be less than or equal to 1000']], ['busy', false]])        // no view, and the draft is not cleared
  })
  it('reads a refusal with no list as a message alone', () => {
    expect(L.refusalParts(new Error('only an Administrator'))).toEqual({ message: 'only an Administrator', problems: [] }); expect(L.refusalParts('x')).toEqual({ message: 'That could not be saved.', problems: [] })
  })
})

describe('the tab', () => {
  it('shows every group with its settings, each with its name in the env file', () => {
    const out = panel()
    for (const g of V.groups) expect(out).toContain(`aria-label="${g.title}"`)
    expect((out.match(/<li aria-label=/g) ?? []).length).toBeGreaterThanOrEqual(65); expect(out).toContain('RUN_BUDGET_USD'); expect(out).toContain('IBM_ICA_HAIKU_MODEL_ID')
  })
  it('shows a secret as Set or Not set with an empty password box, and never its value', () => {
    const out = panel()
    const key = out.slice(out.indexOf('id="setting-ibm_ica_api_key"') - 40, out.indexOf('</li>', out.indexOf('id="setting-ibm_ica_api_key"')))
    expect(key).toContain('type="password"'); expect(key).toContain('value=""'); expect(key).toContain('>Set<'); expect(key).toContain('Type a new value to replace it')
    for (const leaked of ['scratch-key', 'gateway.example']) expect(out).not.toContain(leaked)
  })
  it('shows a normal setting with its value, its unit, and a select for a yes or no and for a choice', () => {
    const out = panel()
    expect(out).toMatch(/id="setting-run_budget_usd"[^>]*value="5.0"/); expect(out).toContain('>USD<'); expect(out).toMatch(/<select id="setting-app_mode"[^>]*>(?:(?!<\/select>)[^])*<option value="replay"/)
    expect(out).toMatch(/<select id="setting-record_live_calls"[^>]*>(?:(?!<\/select>)[^])*<option value="true">Yes/)
  })
  it('keeps what is typed in a box, marks it changed and offers to undo just that one', () => {
    const out = panel({ draft: { run_budget_usd: '9' } })
    expect(out).toMatch(/id="setting-run_budget_usd"[^>]*value="9"/); expect(out).toContain('aria-label="Undo the change to Run budget"'); expect(out).toContain('1 setting changed.')
    expect((out.match(/Undo the change to/g) ?? []).length).toBe(1)
  })
  it('counts the changed settings and disables Save and Discard until something is changed', () => {
    const none = panel()
    expect(none).toContain('No changes yet.'); expect(none).toMatch(/<button[^>]*disabled=""[^>]*>Save<\/button>/); expect(none).toMatch(/<button[^>]*disabled=""[^>]*>Discard changes<\/button>/)
    const some = panel({ draft: { run_budget_usd: '9', replay_set: 'x' } })
    expect(some).toContain('2 settings changed.'); expect(some).not.toMatch(/<button[^>]*disabled=""[^>]*>Save<\/button>/)
  })
  it('says Saving while a save runs and turns every box off', () => {
    const out = panel({ busy: true, draft: { run_budget_usd: '9' } })
    expect(out).toContain('Saving…'); expect(out).toMatch(/<input[^>]*id="setting-run_budget_usd"[^>]*disabled=""/)
  })
  it('turns every box and Save off for someone who may only read, and says so', () => {
    const out = html(<SettingsPanel view={{ ...V, can_edit: false }} draft={{ run_budget_usd: '9' }} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} />)
    expect(out).toContain('Only an Administrator can change settings'); expect(out).toMatch(/<input[^>]*id="setting-run_budget_usd"[^>]*disabled=""/); expect(out).toMatch(/<button[^>]*disabled=""[^>]*>Save<\/button>/)
  })
  it('shows the restart banner while a change is waiting and the saved message after a save', () => {
    const out = html(<SettingsPanel view={SAVED} draft={{}} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} />)
    expect(out).toContain('Restart needed'); expect(out).toContain('Saved. Restart the app for this to take effect.'); expect(out).toContain('Changed: IBM_ICA_API_KEY, RUN_BUDGET_USD.')
    expect(panel()).not.toContain('Restart needed')
  })
  it('lists the earlier versions with a Restore button each, and none when there are none', () => {
    const out = html(<SettingsPanel view={SAVED} draft={{}} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} />)
    expect(out).toContain('Earlier versions'); expect(out).toContain('env-20260101-000000-000001.bak'); expect(out).toContain('>Restore<'); expect(panel()).not.toContain('Earlier versions')
  })
  it('shows a refusal with the variable and the app\'s sentence, as text', () => {
    const out = panel({ error: 'the settings were not saved because the app would not accept them', problems: ['RUN_BUDGET_USD: Input should be less than or equal to 1000', '<b>x</b>'] })
    expect(out).toContain('That could not be saved'); expect(out).toContain('RUN_BUDGET_USD: Input should be less than or equal to 1000'); expect(out).toContain('&lt;b&gt;x&lt;/b&gt;'); expect(out).not.toContain('<b>x</b>')
  })
  it('marks a group that has settings changed from the default', () => {
    const v = clone(V); const s = v.groups.flatMap((g) => g.settings).find((x) => x.key === 'run_budget_usd')!; s.value = '7.0'; s.changed = true
    const out = html(<SettingsPanel view={v} draft={{}} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} />)
    expect(out).toContain('1 changed from the default'); expect(out).toContain('Default: 5.0 USD')
  })
  it('shows text from the server as text', () => {
    const v = clone(V); v.groups[0].settings[0].label = '<img src=x>'; v.groups[0].settings[0].help = '<script>alert(1)</script> help text here'
    const out = html(<SettingsPanel view={v} draft={{}} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} />)
    expect(out).not.toContain('<img src=x>'); expect(out).not.toContain('<script>'); expect(out).toContain('&lt;script&gt;')
  })
})

describe('the Configuration page', () => {
  const project = decodeProject(detailJson)
  const view = (tab: 'users' | 'settings' | 'templates', settings: ReactElement | null) => html(<ConfigurationView project={project} tab={tab} onTab={noop} users={null} me={null} canEdit busy={false} error={null} settings={settings}
    actions={{ onAdd: noop, onRoles: noop, onActive: noop, onApprovers: noop }} />)
  it('shows the settings panel on its tab and not on the others', () => {
    const p = <p>SETTINGS-HERE</p>
    expect(view('settings', p)).toContain('SETTINGS-HERE'); expect(view('users', p)).not.toContain('SETTINGS-HERE'); expect(view('templates', p)).not.toContain('SETTINGS-HERE')
  })
  it('says it is loading until the settings arrive', () => { expect(view('settings', null)).toContain('Loading the settings') })
  it('says nothing is coming any more: both tabs are real', () => {
    expect(view('templates', null)).not.toContain('Coming next'); expect(view('settings', <p>x</p>)).not.toContain('Coming next')
  })
})


describe('even a damaged answer cannot put a secret on the screen', () => {
  const hostile = { ...E.ibm_ica_api_key, value: 'LEAKED-VALUE', default: 'LEAKED-DEFAULT', changed: true }
  it('starts a secret\'s box empty even if the answer carried a value', () => { expect(L.startValue(hostile)).toBe('') })
  it('never notes a default for a secret, and never counts it as changed from the default', () => {
    expect(L.defaultNote(hostile)).toBeNull(); expect(L.changedIn([hostile])).toBe(0)
  })
  it('draws a secret\'s box empty and without its value even then', () => {
    const v = clone(V); v.groups[1].settings = v.groups[1].settings.map((s) => (s.key === 'ibm_ica_api_key' ? hostile : s))
    const out = html(<SettingsPanel view={v} draft={{}} busy={false} error={null} problems={[]} onChange={noop} onReset={noop} onSave={noop} onDiscard={noop} onRestore={noop} />)
    expect(out).not.toContain('LEAKED-VALUE'); expect(out).not.toContain('LEAKED-DEFAULT')
  })
})

describe('what a save and a restore send', () => {
  it('sends only the changed boxes, in the typed name, and the version named', async () => {
    const seen: unknown[][] = []
    const client = { saveSettings: async (a: string, v: Record<string, string>) => { seen.push(['save', a, v]); return SAVED }, restoreSettings: async (a: string, n: string) => { seen.push(['restore', a, n]); return SAVED } }
    const calls = L.settingsCalls(client, 'Root', V, { run_budget_usd: '7', app_mode: 'replay', ibm_ica_api_key: '' })
    await calls.save(); await calls.restore('env-20260101-000000-000001.bak')
    expect(seen).toEqual([['save', 'Root', { run_budget_usd: '7' }], ['restore', 'Root', 'env-20260101-000000-000001.bak']])
  })
  it('changes one box in the draft and leaves the others', () => {
    expect(L.typed({ a: '1' }, 'b', '2')).toEqual({ a: '1', b: '2' }); expect(L.typed({ a: '1' }, 'a', '9')).toEqual({ a: '9' })
  })
})

describe('the buttons of the tab, pressed', () => {
  type El = ReactElement<{ children?: unknown; onClick?: () => void; onChange?: (v: never) => void; disabled?: boolean; 'aria-label'?: string; id?: string; s?: { key: string } }>
  const walk = (node: unknown, test: (e: El) => boolean, out: El[] = []): El[] => {
    if (Array.isArray(node)) { node.forEach((n) => walk(n, test, out)); return out }
    if (node && typeof node === 'object' && 'props' in node) { const el = node as El; if (test(el)) out.push(el); walk(el.props.children, test, out) }
    return out
  }
  const run = (over: Partial<SettingsPanelProps>) => SettingsPanel({ view: SAVED, draft: { run_budget_usd: '9' }, busy: false, error: null, problems: [], onChange: noop, onReset: noop, onSave: noop, onDiscard: noop, onRestore: noop, ...over })
  it('Restore restores the version beside it, and is off for someone who may not save', () => {
    const asked: string[] = []
    const tree = run({ onRestore: (n) => asked.push(n) })
    const [restore] = walk(tree, (e) => e.type === 'button' && e.props.children === 'Restore')
    restore.props.onClick!(); expect(asked).toEqual([SAVED.backups[0].name]); expect(restore.props.disabled).toBe(false)
    const [off] = walk(run({ view: { ...SAVED, can_edit: false } }), (e) => e.type === 'button' && e.props.children === 'Restore')
    expect(off.props.disabled).toBe(true)
    const [busy] = walk(run({ busy: true }), (e) => e.type === 'button' && e.props.children === 'Restore')
    expect(busy.props.disabled).toBe(true)
  })
  it('a box sends its own setting, and Undo undoes its own setting', () => {
    const typedKeys: string[] = [], undone: string[] = []
    const tree = run({ view: V, onChange: (k) => typedKeys.push(k), onReset: (k) => undone.push(k), draft: { run_budget_usd: '9' } })
    const box = walk(tree, (e) => typeof e.type === 'function' && e.props.s?.key === 'run_budget_usd' && typeof e.props.onChange === 'function')       // the Box component: it is not rendered by a bare call of the panel
    expect(box).toHaveLength(1); box[0].props.onChange!({ target: { value: '10' } } as never); expect(typedKeys).toEqual(['run_budget_usd'])
    const [undo] = walk(tree, (e) => e.type === 'button' && e.props['aria-label'] === 'Undo the change to Run budget')
    undo.props.onClick!(); expect(undone).toEqual(['run_budget_usd'])
  })
})


describe('reading the settings as the person who is looking', () => {
  it('asks with the typed name, whatever else changes', async () => {
    const asked: (string | undefined)[] = []
    const client = { settings: async (a?: string) => { asked.push(a); return V } }
    await L.loadSettings(client, 'Parag'); await L.loadSettings(client, 'Ann Lee')
    expect(asked).toEqual(['Parag', 'Ann Lee'])
  })
})
