// The project screen's moving parts in one place: what was loaded, what the person did, and the run being followed. Kept out of the
// component so the component can be rendered statically with any state.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ServerRefused, followEvents, type ArtefactCard, type ArtefactDetail, type ChangeRequest, type Client, type DocumentInfo, type Follow, type PhaseAction,
  type ProjectDetail, type ReviewPaused, type ReviewState_, type SearchResult, type UploadResult,
} from '../api'
import { pastedFilename } from '../lib/documents'
import { applyEvent, idle, isLive, type Progress } from './runProgress'
import { requestStop, runReviewQueue, type QueueItem, type ReviewRun } from './reviewQueue'

const message = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

export function useProjectScreen(client: Client, initial: ProjectDetail, phaseKey: string, actorName: string, reviewsAvailable: boolean) {
  const projectId = initial.id
  const [project, setProject] = useState(initial)
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [cards, setCards] = useState<ArtefactCard[]>([])
  const [open, setOpen] = useState<ArtefactDetail | null>(null)
  const [progress, setProgress] = useState<Progress>(idle)
  const [connected, setConnected] = useState(true)
  const [streamProblem, setStreamProblem] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState<PhaseAction | 'upload' | 'cancel' | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [lastUpload, setLastUpload] = useState<UploadResult | null>(null)
  const [cancelNote, setCancelNote] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResult | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  // S12c: review, the family picker, request changes and edit
  const [reviewState, setReviewState] = useState<ReviewState_ | null>(null)
  const [reviewBusy, setReviewBusy] = useState<string | null>(null)          // the artefact being reviewed, or 'phase'
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [paused, setPaused] = useState<ReviewPaused | null>(null)
  const [chosenFamily, setChosenFamily] = useState<string | null>(null)
  const [reviewRun, setReviewRun] = useState<ReviewRun | null>(null)       // the visible queue behind "Review all"
  const pending = useRef<{ remaining: QueueItem[]; excluded: string[] } | null>(null)
  const stopAsked = useRef(false)
  const [sendingBack, setSendingBack] = useState(false)
  const [changesBusy, setChangesBusy] = useState(false)
  const [changesError, setChangesError] = useState<string | null>(null)
  const [reopening, setReopening] = useState(false)
  const [reopenBusy, setReopenBusy] = useState(false)
  const [reopenError, setReopenError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editBusy, setEditBusy] = useState(false)
  const [editRefusal, setEditRefusal] = useState<{ message: string; problems: string[] } | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const follow = useRef<Follow | null>(null)
  const lastId = useRef(0)
  const live = useRef(true)

  useEffect(() => { live.current = true; return () => { live.current = false; follow.current?.close() } }, [])
  useEffect(() => { setProject(initial) }, [initial])

  const refresh = useCallback(async () => {
    try {
      const [p, a, d, rs] = await Promise.all([client.getProject(projectId), client.listArtefacts(projectId), client.listDocuments(projectId), client.reviewState(projectId, phaseKey)])
      if (!live.current) return
      setProject(p); setCards(a); setDocuments(d); setReviewState(rs)
    } catch (e) { if (live.current) setActionError(message(e, 'The project could not be reloaded.')) }
  }, [client, projectId, phaseKey])

  // One stream per screen, opened from the start of the log: the last run in it is the one shown, and a reload rebuilds the panel.
  const openStream = useCallback(() => {
    follow.current?.close()
    follow.current = followEvents(projectId, lastId.current, {
      onEvent: (e) => {
        lastId.current = Math.max(lastId.current, e.id)
        setProgress((p) => {
          const next = applyEvent(p, e)
          return next
        })
        if (e.type === 'run.finished' || e.type === 'run.stopped' || e.type === 'gate.changed') void refresh()
        if (e.type === 'artefact.finished') void refresh()
      },
      onDropped: () => openStream(),
      onProblem: (m) => setStreamProblem(m),
      onConnectionChange: (c) => setConnected(c),
    })
  }, [projectId, refresh])

  useEffect(() => { void refresh(); openStream() }, [refresh, openStream])

  const open_ = useCallback(async (artefactId: string, version?: number) => {
    try { const d = await client.getArtefact(projectId, artefactId, version); if (live.current) { setOpen(d); setActionError(null) } }
    catch (e) { if (live.current) setActionError(message(e, 'The artefact could not be opened.')) }
  }, [client, projectId])

  const act = useCallback(async (action: PhaseAction) => {
    setBusy(action); setActionError(null); setCancelNote(null)
    try {
      if (action === 'run') await client.startRun(projectId, phaseKey, actorName)
      else if (action === 'finish') await client.finishPhase(projectId, phaseKey, actorName)
      else if (action === 'approve') await client.approvePhase(projectId, phaseKey, actorName)
      await refresh()
    } catch (e) { setActionError(message(e, 'That did not work.')); await refresh() }
    finally { if (live.current) setBusy(null) }
  }, [client, projectId, phaseKey, actorName, refresh])

  const cancel = useCallback(async () => {
    if (!progress.runId) return
    setBusy('cancel')
    try { const a = await client.cancelRun(projectId, progress.runId, actorName); setCancelNote(a.note) }
    catch (e) { setActionError(message(e, 'The run could not be cancelled.')) }
    finally { if (live.current) setBusy(null) }
  }, [client, projectId, progress.runId, actorName])

  const upload = useCallback(async (file: File) => {
    setBusy('upload'); setUploadError(null); setLastUpload(null)
    try { const r = await client.uploadDocument(projectId, file, file.name, actorName); setLastUpload(r); await refresh() }
    catch (e) { setUploadError(message(e, 'The document could not be added.')) }
    finally { if (live.current) setBusy(null) }
  }, [client, projectId, actorName, refresh])

  const paste = useCallback((filename: string, text: string) => upload(new File([text], pastedFilename(filename), { type: 'text/markdown' })), [upload])

  const remove = useCallback(async (doc: DocumentInfo) => {
    setBusy('upload'); setUploadError(null); setLastUpload(null)
    try { await client.removeDocument(projectId, doc.number, actorName); await refresh() }
    catch (e) { setUploadError(message(e, 'The document could not be removed.')) }
    finally { if (live.current) setBusy(null) }
  }, [client, projectId, actorName, refresh])

  // ---- review -----------------------------------------------------------------------------------------------------------

  const reviewOne = useCallback(async (artefactId: string, slot?: string, exclude: string[] = []) => {
    setReviewBusy(artefactId); setReviewError(null)
    try {
      const answer = await client.reviewArtefact(projectId, artefactId, actorName, slot ? { slot, exclude } : {})
      if (answer.paused) { pending.current = null; setPaused(answer); setChosenFamily(null) } else { setPaused(null); await refresh(); if (open?.id === artefactId) await open_(artefactId) }
    } catch (e) { setReviewError(message(e, 'The review could not be run.')) }
    finally { if (live.current) setReviewBusy(null) }
  }, [client, projectId, actorName, refresh, open])

  /** Review a list of artefacts one at a time, visibly. Used for "Review all" and to carry on after a family has been chosen. */
  const runQueue = useCallback(async (queue: QueueItem[], choice: { slot?: string; exclude?: string[] } = {}) => {
    setReviewBusy('phase'); setReviewError(null); setPaused(null); stopAsked.current = false
    try {
      const outcome = await runReviewQueue(queue, {
        review: (id, c) => client.reviewArtefact(projectId, id, actorName, c),
        shouldStop: () => stopAsked.current || !live.current,
        onUpdate: (run) => { if (live.current) setReviewRun(run) },
        afterEach: refresh,                                   // each chip appears as its review finishes
      }, choice)
      if (!live.current) return
      pending.current = outcome.paused ? { remaining: outcome.remaining, excluded: outcome.excluded } : null
      setPaused(outcome.paused); setChosenFamily(null)
      await refresh()
    } catch (e) { setReviewError(message(e, 'The reviews could not be run.')) }
    finally { if (live.current) setReviewBusy(null) }
  }, [client, projectId, actorName, refresh])

  const reviewAll = useCallback(async () => {
    const queue = cards.filter((c) => c.phase_key === phaseKey && c.latest_version !== null).map((c) => ({ id: c.id, name: c.title }))
    await runQueue(queue)
  }, [cards, phaseKey, runQueue])

  /** The reviewer could not run and the person chose another family: carry on with the artefacts that are left, using it. */
  const reviewWithChosen = useCallback(async () => {
    if (!paused || !chosenFamily) return
    const left = pending.current
    if (left && reviewRun && !reviewRun.stopRequested) await runQueue(left.remaining, { slot: chosenFamily, exclude: left.excluded })
    else await reviewOne(paused.artefact_id, chosenFamily, [paused.slot])       // a single artefact's review, not part of a queue
  }, [paused, chosenFamily, reviewOne, runQueue, reviewRun])

  const stopReviews = useCallback(() => { stopAsked.current = true; setReviewRun((run) => (run ? requestStop(run) : run)) }, [])
  const dismissReviews = useCallback(() => { setReviewRun(null); pending.current = null }, [])

  // ---- send back, re-run, edit -------------------------------------------------------------------------------------------------

  const sendBack = useCallback(async (input: ChangeRequest) => {
    setChangesBusy(true); setChangesError(null)
    try { await client.requestChanges(projectId, phaseKey, actorName, input); setSendingBack(false); await refresh() }
    catch (e) { setChangesError(message(e, 'The changes could not be sent.')) }
    finally { if (live.current) setChangesBusy(false) }
  }, [client, projectId, phaseKey, actorName, refresh])

  const rerunNotes = useCallback(async () => {
    setBusy('run'); setActionError(null)
    try { await client.rerun(projectId, phaseKey, actorName); await refresh() }
    catch (e) { setActionError(message(e, 'The re-run could not be started.')); await refresh() }
    finally { if (live.current) setBusy(null) }
  }, [client, projectId, phaseKey, actorName, refresh])

  const rerunStale = useCallback(async () => {
    setBusy('run'); setActionError(null)
    try { await client.rerunStale(projectId, phaseKey, actorName); await refresh() }
    catch (e) { setActionError(message(e, 'The re-run could not be started.')); await refresh() }
    finally { if (live.current) setBusy(null) }
  }, [client, projectId, phaseKey, actorName, refresh])

  const reopen = useCallback(async (reason: string) => {
    setReopenBusy(true); setReopenError(null)
    try { await client.reopenPhase(projectId, phaseKey, actorName, reason); setReopening(false); await refresh() }
    catch (e) { setReopenError(message(e, 'The phase could not be reopened.')) }
    finally { if (live.current) setReopenBusy(false) }
  }, [client, projectId, phaseKey, actorName, refresh])

  const saveEdit = useCallback(async (body: string, note: string) => {
    if (!open) return
    setEditBusy(true); setEditRefusal(null); setEditError(null)
    try {
      await client.editArtefact(projectId, open.id, actorName, body, note)
      setEditing(false); await refresh(); await open_(open.id)
    } catch (e) {
      // A refusal lists every reason, and the text stays in the box. Anything else is one sentence.
      if (e instanceof ServerRefused && e.problems.length) setEditRefusal({ message: e.message, problems: e.problems })
      else setEditError(message(e, 'The edit could not be saved.'))
    } finally { if (live.current) setEditBusy(false) }
  }, [client, projectId, actorName, open, refresh, open_])

  const search = useCallback(async () => {
    setSearching(true); setSearchError(null)
    try { const r = await client.search(projectId, query); if (live.current) setResult(r) }
    catch (e) { if (live.current) { setResult(null); setSearchError(message(e, 'The search failed.')) } }
    finally { if (live.current) setSearching(false) }
  }, [client, projectId, query])

  return {
    project, documents, cards, open, progress, connected, streamProblem, actionError, busy, uploadError, lastUpload, cancelNote, query, result, searchError, searching,
    runLive: isLive(progress), setQuery, act, cancel, upload, paste, remove, search, openArtefact: open_, close: () => { setOpen(null); setEditing(false) }, refresh,
    reviewsAvailable, reviewState, reviewBusy, reviewError, paused, chosenFamily, setChosenFamily, reviewOne, reviewAll, reviewWithChosen, reviewRun, stopReviews, dismissReviews,
    sendingBack, setSendingBack, changesBusy, changesError, sendBack, rerunNotes, rerunStale,
    reopening, setReopening: (on: boolean) => { setReopening(on); setReopenError(null) }, reopenBusy, reopenError, reopen,
    editing, setEditing: (on: boolean) => { setEditing(on); setEditRefusal(null); setEditError(null) }, editBusy, editRefusal, editError, saveEdit,
  }
}
