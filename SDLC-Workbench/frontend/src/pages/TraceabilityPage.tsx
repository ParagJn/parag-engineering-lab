import { useEffect, useState } from 'react'
import type { Client, ProjectDetail } from '../api'
import type { TraceItem, Traceability } from '../api/trace'
import { ItemTrace, TraceabilityPanel } from '../components/TraceabilityPanel'
import { Notice, Spinner } from '../components/Notice'
import { buildHash } from '../lib/router'

type Load<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed'; message: string }

function useLoaded<T>(load: () => Promise<T>, deps: unknown[]): Load<T> {
  const [result, setResult] = useState<Load<T>>({ state: 'loading' })
  useEffect(() => {
    let live = true
    setResult({ state: 'loading' })
    load().then((value) => live && setResult({ state: 'ready', value })).catch((e) => live && setResult({ state: 'failed', message: e instanceof Error ? e.message : 'That could not be loaded.' }))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return result
}

/** The Traceability tab of a project: all the gaps and the chain table, or the trace of one item when an ID is in the address. */
export function TraceabilityPage({ client, id, item }: { client: Client; id: string; item: string | null }) {
  const project = useLoaded<ProjectDetail>(() => client.getProject(id), [id])
  const all = useLoaded<Traceability>(() => client.traceability(id), [id])
  const one = useLoaded<TraceItem | null>(() => (item ? client.traceItem(id, item) : Promise.resolve(null)), [id, item])
  if (project.state === 'loading' || all.state === 'loading' || one.state === 'loading') return <Spinner label="Working out the traceability" />
  if (project.state === 'failed') return <Notice tone="error" title="The project could not be loaded">{project.message}</Notice>
  if (all.state === 'failed') return <Notice tone="error" title="The traceability could not be worked out">{all.message}</Notice>
  const name = project.value.name
  if (item) {
    return (
      <div className="space-y-4">
        <a href={buildHash({ name: 'traceability', id, item: null })} className="text-sm text-sky-800">Back to the traceability of {name}</a>
        {one.state === 'failed' ? <Notice tone="warn" title="That item could not be shown">{one.message}</Notice> : one.value && <ItemTrace trace={one.value} projectId={id} />}
      </div>
    )
  }
  return <TraceabilityPanel data={all.value} projectId={id} projectName={name} />
}
