import { useCallback, useEffect, useState, type ReactElement } from 'react'
import { ArrowLeft } from 'lucide-react'
import type { Client, ProjectDetail } from '../api'
import type { Me, UsersList } from '../api/users'
import { Notice, Spinner } from '../components/Notice'
import { SettingsPanel } from '../components/SettingsPanel'
import type { SettingsView } from '../api/settings'
import { loadSettings, reset, runSave, settingsCalls, typed, type Draft } from '../lib/settings'
import { TemplatesPanel } from '../components/TemplatesPanel'
import type { TemplatesView } from '../api/templates'
import { loadTemplates, runTemplateChange, templateActions } from '../lib/templates'
import { PhaseRail } from '../components/PhaseRail'
import { UsersPanel } from '../components/UsersPanel'
import { buildHash } from '../lib/router'
import { canEditUsers, runChange, usersActions } from '../lib/users'

type Load<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed'; message: string }
export const TABS = [{ key: 'users', label: 'Users and roles' }, { key: 'settings', label: 'System settings' }, { key: 'templates', label: 'Templates' }] as const
export type TabKey = (typeof TABS)[number]['key']

/** Configuration (S23): reached from the Setup phase. Users and roles and the system settings are global to the app; templates belong to this project. */
export function ConfigurationView({ project, tab, onTab, users, me, canEdit, busy, error, actions, settings = null, templates = null }: {
  project: ProjectDetail; tab: TabKey; onTab: (t: TabKey) => void; users: UsersList | null; me: Me | null; canEdit: boolean; busy: boolean; error: string | null
  settings?: ReactElement | null
  templates?: ReactElement | null
  actions: { onAdd: (n: string, r: string[]) => void; onRoles: (n: string, r: string[]) => void; onActive: (n: string, a: boolean) => void; onApprovers: (p: string, r: string[]) => void }
}) {
  return (
    <section>
      <a href={buildHash({ name: 'project', id: project.id, phase: 'setup' })} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 no-underline hover:text-slate-900"><ArrowLeft size={14} aria-hidden /> Back to {project.name}</a>
      <h1 className="mb-4 text-2xl font-bold">Configuration</h1>
      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <PhaseRail projectId={project.id} phases={project.phases} selected="setup" onConfiguration />
        <div className="min-w-0 space-y-4">
          <div role="tablist" aria-label="Configuration" className="flex flex-wrap gap-2">
            {TABS.map((t) => (
              <button key={t.key} role="tab" type="button" aria-selected={tab === t.key} onClick={() => onTab(t.key)}
                className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${tab === t.key ? 'bg-slate-900 text-white' : 'border border-slate-300 text-slate-700'}`}>{t.label}</button>
            ))}
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            {tab === 'users' ? (
              users ? <UsersPanel list={users} me={me} canEdit={canEdit} busy={busy} error={error} {...actions} /> : <Spinner label="Loading the Users list" />
            ) : tab === 'settings' ? (
              settings ?? <Spinner label="Loading the settings" />
            ) : (
              templates ?? <Spinner label="Loading the templates" />
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export function ConfigurationPage({ client, id, actorName }: { client: Client; id: string; actorName: string }) {
  const [project, setProject] = useState<Load<ProjectDetail>>({ state: 'loading' })
  const [users, setUsers] = useState<UsersList | null>(null)
  const [me, setMe] = useState<Me | null>(null)
  const [tab, setTab] = useState<TabKey>('users')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<SettingsView | null>(null)
  const [draft, setDraft] = useState<Draft>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<{ message: string | null; problems: string[] }>({ message: null, problems: [] })
  const [tpl, setTpl] = useState<TemplatesView | null>(null)
  const [tplBusy, setTplBusy] = useState(false)
  const [tplError, setTplError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const [list, who] = await Promise.all([client.users(), client.me(actorName)])
    setUsers(list); setMe(who)
  }, [client, actorName])

  useEffect(() => {
    let live = true
    client.getProject(id).then((value) => live && setProject({ state: 'ready', value })).catch((e) => live && setProject({ state: 'failed', message: e instanceof Error ? e.message : 'The project could not be loaded.' }))
    refresh().catch((e) => live && setError(e instanceof Error ? e.message : 'The Users list could not be loaded.'))
    loadSettings(client, actorName).then((v) => live && setView(v)).catch((e) => live && setSaveError({ message: e instanceof Error ? e.message : 'The settings could not be loaded.', problems: [] }))
    loadTemplates(client, id, actorName).then((v) => live && setTpl(v)).catch((e) => live && setTplError(e instanceof Error ? e.message : 'The templates could not be loaded.'))
    return () => { live = false }
  }, [client, id, refresh, actorName])

  const change = (what: () => Promise<unknown>) => { void runChange(what, { setBusy, setError, reload: refresh }) }

  if (project.state === 'loading') return <Spinner label="Loading the project" />
  if (project.state === 'failed') return <Notice tone="error" title="The project could not be loaded">{project.message}</Notice>
  const save = () => { if (view) void runSave(settingsCalls(client, actorName, view, draft).save, { setBusy: setSaving, setError: (message, problems) => setSaveError({ message, problems }), setView, clearDraft: () => setDraft({}) }) }
  const restore = (name: string) => { if (view) void runSave(() => settingsCalls(client, actorName, view, draft).restore(name), { setBusy: setSaving, setError: (message, problems) => setSaveError({ message, problems }), setView, clearDraft: () => setDraft({}) }) }
  const panel = view ? (
    <SettingsPanel view={view} draft={draft} busy={saving} error={saveError.message} problems={saveError.problems} onChange={(k, v) => setDraft(typed(draft, k, v))}
      onReset={(k) => setDraft(reset(draft, k))} onSave={save} onDiscard={() => setDraft({})} onRestore={restore} />
  ) : saveError.message ? <Notice tone="error" title="The settings could not be loaded">{saveError.message}</Notice> : null
  const tplUi = { setBusy: setTplBusy, setError: setTplError, setView: setTpl }
  const tplDo = templateActions(client, id, actorName)
  const templates = tpl ? (
    <TemplatesPanel projectId={id} view={tpl} busy={tplBusy} error={tplError}
      onUpload={(category, file, filename) => { void runTemplateChange(() => tplDo.upload(category, file, filename), tplUi) }}
      onRemove={(category) => { void runTemplateChange(() => tplDo.remove(category), tplUi) }} />
  ) : tplError ? <Notice tone="error" title="The templates could not be loaded">{tplError}</Notice> : null
  return (
    <ConfigurationView settings={panel} templates={templates} project={project.value} tab={tab} onTab={setTab} users={users} me={me} canEdit={canEditUsers(users, me) && !!actorName} busy={busy} error={error}
      actions={usersActions(client, actorName, change)} />
  )
}
