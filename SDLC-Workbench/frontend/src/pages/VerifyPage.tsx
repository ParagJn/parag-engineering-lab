import { useCallback, useEffect, useState } from 'react'
import type { Client, ProjectDetail } from '../api'
import type { VerifyDetail, VerifyList } from '../api/verify'
import { ServerRefused } from '../api'
import { VerifyPanel } from '../components/VerifyPanel'
import { Notice, Spinner } from '../components/Notice'
import { designChanged } from '../lib/verify'
import { loadPaths, savePaths } from '../lib/verifyPaths'
import { browserStore } from '../lib/actor'

type Load<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed'; message: string }

/** Build Verify (S20): paste the folders of the real build, press Check, see the drift. Reading only; the server never runs what it reads. */
export function VerifyPage({ client, id, actorName }: { client: Client; id: string; actorName: string }) {
  const [project, setProject] = useState<Load<ProjectDetail>>({ state: 'loading' })
  const [list, setList] = useState<VerifyList | null>(null)
  const [detail, setDetail] = useState<VerifyDetail | null>(null)
  const [backend, setBackend] = useState(() => loadPaths(browserStore(), id).backend)
  const [frontend, setFrontend] = useState(() => loadPaths(browserStore(), id).frontend)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [changed, setChanged] = useState(false)

  const refresh = useCallback(async (open?: number) => {
    const runs = await client.verifyRuns(id)
    setList(runs)
    const target = open ?? runs.runs[0]?.id
    setDetail(target === undefined ? null : await client.verifyRun(id, target))
  }, [client, id])

  useEffect(() => {
    let live = true
    client.getProject(id).then((value) => live && setProject({ state: 'ready', value })).catch((e) => live && setProject({ state: 'failed', message: e instanceof Error ? e.message : 'The project could not be loaded.' }))
    refresh().catch((e) => live && setError(e instanceof Error ? e.message : 'The earlier runs could not be loaded.'))
    return () => { live = false }
  }, [client, id, refresh])

  useEffect(() => {
    // Has the design moved on since the run on show? The run's own design versions are compared with the project's artefacts now. Nothing is run.
    if (!detail) { setChanged(false); return }
    client.listArtefacts(id).then((cards) => {
      const now: Record<string, number> = {}
      for (const a of cards) if (a.latest_version) now[a.id] = a.latest_version
      setChanged(designChanged(detail, now))
    }).catch(() => setChanged(false))
  }, [client, id, detail])

  const run = async () => {
    setBusy(true); setError(null)
    try {
      const made = await client.runVerify(id, actorName, backend.trim(), frontend.trim() || null)
      savePaths(browserStore(), id, { backend: backend.trim(), frontend: frontend.trim() })
      await refresh(made.id)
    } catch (e) {
      setError(e instanceof ServerRefused || e instanceof Error ? e.message : 'The check could not be run.')
    } finally { setBusy(false) }
  }

  if (project.state === 'loading') return <Spinner label="Loading the project" />
  if (project.state === 'failed') return <Notice tone="error" title="The project could not be loaded">{project.message}</Notice>
  return (
    <VerifyPanel
      projectId={id} projectName={project.value.name} advice={list?.advice ?? ''} runs={list?.runs ?? []} detail={detail} designChanged={changed} busy={busy} error={error}
      backend={backend} frontend={frontend} canRun={!!actorName} onBackend={setBackend} onFrontend={setFrontend} onRun={run}
      onOpenRun={(runId) => { setError(null); client.verifyRun(id, runId).then(setDetail).catch((e) => setError(e instanceof Error ? e.message : 'That run could not be loaded.')) }}
    />
  )
}
