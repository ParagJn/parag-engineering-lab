import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import {
  BackendUnreachable, makeClient, type Catalogue, type ModeInfo, type Plan, type ProjectDetail, type ProjectSummary, type Sample,
} from './api'
import { Shell } from './components/Shell'
import { NamePrompt } from './components/NamePrompt'
import { Notice, Spinner } from './components/Notice'
import { browserStore, loadName, saveName } from './lib/actor'
import { buildHash } from './lib/router'
import { fileProblem, pastedFilename, type StagedDocument } from './lib/documents'
import { createPayload, initialWizard, selectionOf } from './lib/wizard'
import { HomePage } from './pages/HomePage'
import { ProjectPage } from './pages/ProjectPage'
import { TraceabilityPage } from './pages/TraceabilityPage'
import { VerifyPage } from './pages/VerifyPage'
import { WizardPage } from './pages/WizardPage'
import { makeWizardReducer } from './state/wizardReducer'
import { useRoute } from './state/useRoute'
import { useProjectScreen } from './state/useProjectScreen'

const client = makeClient()

/** One of: still loading, loaded, or failed with a sentence a person can act on. */
type Load<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed'; message: string; unreachable: boolean }

function failure(error: unknown): { state: 'failed'; message: string; unreachable: boolean } {
  return { state: 'failed', message: error instanceof Error ? error.message : 'Something went wrong.', unreachable: error instanceof BackendUnreachable }
}

function useLoad<T>(load: () => Promise<T>, deps: unknown[]): [Load<T>, () => void] {
  const [result, setResult] = useState<Load<T>>({ state: 'loading' })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setResult({ state: 'loading' })
    load().then((value) => live && setResult({ state: 'ready', value })).catch((error) => live && setResult(failure(error)))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return [result, () => setTick((n) => n + 1)]
}

export default function App() {
  const [route, go] = useRoute()
  const [actorName, setActorName] = useState(() => loadName(browserStore()))
  const [asking, setAsking] = useState(false)
  const [flash, setFlash] = useState<{ id: string; message: string } | null>(null)
  const [modeLoad] = useLoad(() => client.mode(), [])

  const mode = modeLoad.state === 'ready' ? modeLoad.value.mode : null
  const needName = !actorName || asking

  const saveActor = (name: string) => { saveName(browserStore(), name); setActorName(name.trim().split(/\s+/).join(' ')); setAsking(false) }

  return (
    <Shell mode={mode} actorName={actorName} onChangeName={() => setAsking(true)}>
      {modeLoad.state === 'failed' && modeLoad.unreachable ? (
        <Notice tone="error" title="The backend is not reachable">{modeLoad.message}</Notice>
      ) : needName ? (
        <NamePrompt initial={actorName} onSave={saveActor} onCancel={actorName ? () => setAsking(false) : undefined} />
      ) : route.name === 'home' ? <Home actorName={actorName} />
        : route.name === 'new' ? <NewProject key={route.sample ? 'sample' : 'blank'} useSample={!!route.sample} actorName={actorName} modeInfo={modeLoad.state === 'ready' ? modeLoad.value : null} onCreated={(id, note) => { setFlash(note ? { id, message: note } : null); go({ name: 'project', id, phase: null }) }} />
        : route.name === 'traceability' ? <TraceabilityPage key={route.id} client={client} id={route.id} item={route.item} />
        : route.name === 'verify' ? <VerifyPage key={route.id} client={client} id={route.id} actorName={actorName} />
        : route.name === 'project' ? <OneProject id={route.id} phase={route.phase} actorName={actorName} mode={mode} reviewsAvailable={modeLoad.state === 'ready' && modeLoad.value.reviews_available} flash={flash?.id === route.id ? flash.message : null} />
        : <Notice tone="info" title="That page does not exist"><a href={buildHash({ name: 'home' })} className="underline">Back to projects</a></Notice>}
    </Shell>
  )
}

function Home({ actorName }: { actorName: string }) {
  const [showArchived, setShowArchived] = useState(false)
  const [projects, reload] = useLoad<ProjectSummary[]>(() => client.listProjects({ archived: showArchived }), [showArchived])
  const [confirming, setConfirming] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const change = async (id: string, work: () => Promise<unknown>) => {
    setBusyId(id); setError(null)
    try { await work(); setConfirming(null); reload() }
    catch (e) { setError(e instanceof Error ? e.message : 'That did not work.'); setConfirming(null) }
    finally { setBusyId(null) }
  }
  if (projects.state === 'loading') return <Spinner label="Loading projects" />
  if (projects.state === 'failed') return <Notice tone="error" title="Projects could not be loaded">{projects.message} <button type="button" onClick={reload} className="underline">Try again</button></Notice>
  return (
    <HomePage
      projects={projects.value} showArchived={showArchived} confirming={confirming} busyId={busyId} error={error} canChange={!!actorName}
      onShowArchived={(show) => { setConfirming(null); setError(null); setShowArchived(show) }}
      onAskArchive={(id) => { setError(null); setConfirming(id) }} onCancel={() => setConfirming(null)}
      onArchive={(id) => change(id, () => client.archiveProject(id, actorName))} onRestore={(id) => change(id, () => client.restoreProject(id, actorName))}
    />
  )
}

function OneProject({ id, phase, actorName, mode, reviewsAvailable, flash }: { id: string; phase: string | null; actorName: string; mode: 'replay' | 'live' | null; reviewsAvailable: boolean; flash: string | null }) {
  const [project, reload] = useLoad<ProjectDetail>(() => client.getProject(id), [id])
  if (project.state === 'loading') return <Spinner label="Loading the project" />
  if (project.state === 'failed') return <Notice tone="error" title="The project could not be loaded">{project.message} <button type="button" onClick={reload} className="underline">Try again</button></Notice>
  return <LoadedProject key={id} initial={project.value} phase={phase} actorName={actorName} mode={mode} reviewsAvailable={reviewsAvailable} flash={flash} />
}

/** The project once it has loaded: it keeps its own copy fresh as runs and approvals change it. */
function LoadedProject({ initial, phase, actorName, mode, reviewsAvailable, flash }: { initial: ProjectDetail; phase: string | null; actorName: string; mode: 'replay' | 'live' | null; reviewsAvailable: boolean; flash: string | null }) {
  const first = initial.phases.find((p) => p.key === phase) ?? initial.phases.find((p) => p.status !== 'approved' && p.artefacts.length > 0) ?? initial.phases[0]
  const screen = useProjectScreen(client, initial, first.key, actorName, reviewsAvailable)
  const current = screen.project.phases.find((p) => p.key === first.key) ?? first
  return (
    <>
      {flash && <div className="mb-3"><Notice tone="warn" title="One thing did not work">{flash}</Notice></div>}
      {mode && mode !== screen.project.mode && <div className="mb-3"><Notice tone="warn" title="This project was made in a different mode">It was created in {screen.project.mode.toUpperCase()} mode; this server is now in {mode.toUpperCase()} mode, and that is what runs will use.</Notice></div>}
      <ProjectPage
        project={screen.project} phaseKey={current.key} canChange={!!actorName}
        screen={{
          documents: screen.documents, cards: screen.cards, open: screen.open, progress: screen.progress, connected: screen.connected, streamProblem: screen.streamProblem,
          actionError: screen.actionError, busy: screen.busy, uploadError: screen.uploadError, lastUpload: screen.lastUpload, cancelNote: screen.cancelNote, query: screen.query,
          result: screen.result, searchError: screen.searchError, searching: screen.searching, runLive: screen.runLive, onQuery: screen.setQuery, onSearch: screen.search,
          onAct: screen.act, onCancel: screen.cancel, onUpload: screen.upload, onPaste: screen.paste, onRemove: screen.remove, onOpen: (a) => screen.openArtefact(a), onDownload: screen.downloadFiles, downloadNote: screen.downloadNote, checklist: screen.checklist, checkBusy: screen.checkBusy, checkError: screen.checkError, onAnswerCheck: screen.answerCheck,
          onVersion: (n) => screen.open && screen.openArtefact(screen.open.id, n), onClose: screen.close,
          review: {
            state: screen.reviewState, available: screen.reviewsAvailable, busy: screen.reviewBusy, error: screen.reviewError, paused: screen.paused, chosenFamily: screen.chosenFamily,
            sendingBack: screen.sendingBack, changesBusy: screen.changesBusy, changesError: screen.changesError, editing: screen.editing, editingFile: screen.editingFile, editBusy: screen.editBusy,
            editRefusal: screen.editRefusal, editError: screen.editError, onReviewOne: (id) => screen.reviewOne(id), onReviewAll: screen.reviewAll, run: screen.reviewRun, onStopReviews: screen.stopReviews, onDismissReviews: screen.dismissReviews, onChooseFamily: screen.setChosenFamily,
            onReviewWithChosen: screen.reviewWithChosen, onStartSendBack: () => screen.setSendingBack(true), reopening: screen.reopening, reopenBusy: screen.reopenBusy, reopenError: screen.reopenError, onStartReopen: () => screen.setReopening(true), onCancelReopen: () => screen.setReopening(false), onReopen: screen.reopen, onCancelSendBack: () => screen.setSendingBack(false), onSendBack: screen.sendBack,
            onRerunNotes: screen.rerunNotes, onRerunStale: screen.rerunStale, onStartEdit: () => screen.setEditing(true), onStartEditFile: screen.startEditFile, onCancelEdit: () => screen.setEditing(false), onSaveEdit: screen.saveEdit,
          },
        }}
      />
    </>
  )
}

function NewProject({ actorName, modeInfo, useSample, onCreated }: { actorName: string; modeInfo: ModeInfo | null; useSample: boolean; onCreated: (id: string, note?: string) => void }) {
  const [catalogue] = useLoad<Catalogue>(() => client.catalogue(), [])
  const [sample] = useLoad<Sample | null>(() => (useSample ? client.sample() : Promise.resolve(null)), [useSample])
  if (catalogue.state === 'loading' || sample.state === 'loading' || (catalogue.state === 'ready' && !modeInfo)) return <Spinner label="Loading the catalogue" />
  if (catalogue.state === 'failed') return <Notice tone="error" title="The catalogue could not be loaded">{catalogue.message}</Notice>
  if (sample.state === 'failed') return <Notice tone="error" title="The sample could not be loaded">{sample.message}</Notice>
  return <Wizard catalogue={catalogue.value} modeInfo={modeInfo!} actorName={actorName} sample={sample.value} onCreated={onCreated} />
}

function Wizard({ catalogue, modeInfo, actorName, sample, onCreated }: { catalogue: Catalogue; modeInfo: ModeInfo; actorName: string; sample: Sample | null; onCreated: (id: string, note?: string) => void }) {
  const reducer = useMemo(() => makeWizardReducer(catalogue), [catalogue])
  const [state, dispatch] = useReducer(reducer, catalogue, (c) => (sample ? { ...initialWizard(c), name: sample.name, brief: sample.brief } : initialWizard(c)))
  const [plan, setPlan] = useState<Plan | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [documentProblem, setDocumentProblem] = useState<string | null>(null)
  const staged = useRef(0)

  // The server says what the selection means. The screen never works it out.
  const selectionKey = JSON.stringify(selectionOf(state, catalogue))
  useEffect(() => {
    let live = true
    client.previewPlan(JSON.parse(selectionKey)).then((p) => { if (live) { setPlan(p); setPlanError(null) } })
      .catch((e) => { if (live) { setPlan(null); setPlanError(e instanceof Error ? e.message : 'The selection could not be checked.') } })
    return () => { live = false }
  }, [selectionKey])

  const create = useCallback(async () => {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const made = await client.createProject(createPayload(state, catalogue), actorName)
      // The project exists now. Each document is added on its own, and any that cannot be added is named on the project page rather than
      // hidden behind the redirect: the project is real and usable, and the person can add the rest there.
      const toAdd: { filename: string; blob: Blob }[] = [
        ...(sample ? [{ filename: sample.document.filename, blob: new Blob([sample.document.text], { type: 'text/markdown' }) }] : []),
        ...state.documents.map((d) => ({ filename: d.filename, blob: d.blob })),
      ]
      const failed: string[] = []
      for (const doc of toAdd) {
        try { await client.uploadDocument(made.id, doc.blob, doc.filename, actorName) }
        catch (e) { failed.push(`${doc.filename} (${e instanceof Error ? e.message : 'unknown problem'})`) }
      }
      const note = failed.length ? `The project was created, but ${failed.length === 1 ? 'a document' : `${failed.length} documents`} could not be added: ${failed.join('; ')}. Add ${failed.length === 1 ? 'it' : 'them'} with “Upload a document” on this page.` : undefined
      onCreated(made.id, note)
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'The project could not be created.')
    } finally {
      setSubmitting(false)
    }
  }, [state, catalogue, actorName, sample, onCreated])

  const addFiles = useCallback((files: File[]) => {
    let problem: string | null = null
    for (const file of files) {
      const why = fileProblem(file.name, file.size, state.documents.length + staged.current)
      if (why) { problem = why; continue }
      staged.current += 1
      dispatch({ type: 'add-document', document: { key: `f${Date.now()}-${staged.current}`, filename: file.name, size: file.size, blob: file } })
    }
    staged.current = 0
    setDocumentProblem(problem)
  }, [state.documents.length])
  const pasteDocument = useCallback((filename: string, text: string) => {
    const name = pastedFilename(filename)
    const blob = new Blob([text], { type: 'text/markdown' })
    const why = fileProblem(name, blob.size, state.documents.length)
    setDocumentProblem(why)
    if (!why) dispatch({ type: 'add-document', document: { key: `p${Date.now()}`, filename: name, size: blob.size, blob } satisfies StagedDocument })
  }, [state.documents.length])

  return (
    <WizardPage
      state={state} catalogue={catalogue} modeInfo={modeInfo} plan={plan} planError={planError} submitError={submitError} submitting={submitting} sample={sample?.document ?? null}
      onChange={(patch) => dispatch({ type: 'edit', patch })}
      onToggleArtefact={(phase, artefact) => dispatch({ type: 'toggle-artefact', phase, artefact })}
      onToggleConnector={(connector) => dispatch({ type: 'toggle-connector', connector })}
      onAddFiles={addFiles} onPasteDocument={pasteDocument} onRemoveDocument={(key) => dispatch({ type: 'remove-document', key })} documentProblem={documentProblem}
      onBack={() => dispatch({ type: 'back' })} onNext={() => dispatch({ type: 'next' })} onCreate={create}
    />
  )
}
