import { ArrowLeft } from 'lucide-react'
import type { ArtefactCard, ArtefactDetail, ChangeRequest, DocumentInfo, PhaseAction, ReviewPaused, ReviewState_, SearchResult, UploadResult } from '../api'
import { ArtefactCardView } from '../components/ArtefactCard'
import { ArtefactReader } from '../components/ArtefactReader'
import { EditArtefact } from '../components/EditArtefact'
import { FamilyPicker } from '../components/FamilyPicker'
import { RequestChangesForm } from '../components/RequestChangesForm'
import { ReviewChip } from '../components/ReviewChip'
import { ReviewProgress } from '../components/ReviewProgress'
import { ReopenForm, laterStartedNames } from '../components/ReopenForm'
import { StaleBanner } from '../components/StaleBanner'
import type { ReviewRun } from '../state/reviewQueue'
import { ModeChip, SimulatedBadge, StatusPill } from '../components/Badges'
import { DocumentsPanel } from '../components/DocumentsPanel'
import { Notice } from '../components/Notice'
import { PhaseRail } from '../components/PhaseRail'
import { RunPanel } from '../components/RunPanel'
import { SearchBox } from '../components/SearchBox'
import type { ProjectDetail } from '../api'
import { CONNECTOR_LABEL, count } from '../lib/format'
import { actionSpecs, pressRoute } from '../lib/phaseActions'
import type { Progress } from '../state/runProgress'
import { ApprovalSummary, openCount } from '../components/ApprovalSummary'

/** Everything the project screen shows beyond the project itself. The container supplies it; a test can supply any state. */
export interface ProjectScreen {
  documents: DocumentInfo[]
  cards: ArtefactCard[]
  open: ArtefactDetail | null
  progress: Progress
  connected: boolean
  streamProblem: string | null
  actionError: string | null
  busy: PhaseAction | 'upload' | 'cancel' | null
  uploadError: string | null
  lastUpload: UploadResult | null
  cancelNote: string | null
  query: string
  result: SearchResult | null
  searchError: string | null
  searching: boolean
  runLive: boolean
  onQuery: (q: string) => void
  onSearch: () => void
  onAct: (action: PhaseAction) => void
  onCancel: () => void
  onUpload: (file: File) => void
  onPaste: (filename: string, text: string) => void
  onRemove: (doc: DocumentInfo) => void
  onOpen: (artefactId: string) => void
  onVersion: (number: number) => void
  onClose: () => void
  // S12c
  review: ReviewScreen
}

/** Everything the review, send-back and edit parts of the screen need. A null `state` means it has not loaded yet. */
export interface ReviewScreen {
  state: ReviewState_ | null
  available: boolean
  busy: string | null
  error: string | null
  paused: ReviewPaused | null
  chosenFamily: string | null
  sendingBack: boolean
  reopening: boolean
  reopenBusy: boolean
  reopenError: string | null
  changesBusy: boolean
  changesError: string | null
  editing: boolean
  editBusy: boolean
  editRefusal: { message: string; problems: string[] } | null
  editError: string | null
  onReviewOne: (artefactId: string) => void
  onReviewAll: () => void
  /** The visible queue behind "Review all", or null when none is showing. */
  run: ReviewRun | null
  onStopReviews: () => void
  onDismissReviews: () => void
  onChooseFamily: (slot: string) => void
  onReviewWithChosen: () => void
  onStartSendBack: () => void
  onStartReopen: () => void
  onCancelReopen: () => void
  onReopen: (reason: string) => void
  onCancelSendBack: () => void
  onSendBack: (input: ChangeRequest) => void
  onRerunNotes: () => void
  onRerunStale: () => void
  onStartEdit: () => void
  onCancelEdit: () => void
  onSaveEdit: (body: string, note: string) => void
}

const none = () => {}
export const emptyReview: ReviewScreen = {
  state: null, available: false, busy: null, error: null, paused: null, chosenFamily: null, sendingBack: false, reopening: false, reopenBusy: false, reopenError: null, changesBusy: false, changesError: null,
  editing: false, editBusy: false, editRefusal: null, editError: null, onReviewOne: none, onReviewAll: none, run: null, onStopReviews: none, onDismissReviews: none, onChooseFamily: none, onReviewWithChosen: none,
  onStartSendBack: none, onStartReopen: none, onCancelReopen: none, onReopen: none, onCancelSendBack: none, onSendBack: none, onRerunNotes: none, onRerunStale: none, onStartEdit: none, onCancelEdit: none, onSaveEdit: none,
}

export const emptyScreen: ProjectScreen = {
  documents: [], cards: [], open: null,
  progress: { runId: null, phase: null, status: 'idle', stopReason: null, failureNote: null, rows: [], lastEventId: 0, concurrency: null, capUsd: null, capSeconds: null, costUsd: 0, costKnown: true, totals: null },
  connected: true, streamProblem: null, actionError: null, busy: null, uploadError: null, lastUpload: null, cancelNote: null, query: '', result: null, searchError: null,
  searching: false, runLive: false, onQuery: () => {}, onSearch: () => {}, onAct: () => {}, onCancel: () => {}, onUpload: () => {}, onPaste: () => {}, onRemove: () => {}, onOpen: () => {},
  onVersion: () => {}, onClose: () => {}, review: emptyReview,
}

export function ProjectPage({ project, phaseKey, screen = emptyScreen, canChange = true }: { project: ProjectDetail; phaseKey: string | null; screen?: ProjectScreen; canChange?: boolean }) {
  const phase = project.phases.find((p) => p.key === phaseKey) ?? project.phases.find((p) => p.status !== 'approved' && p.artefacts.length > 0) ?? project.phases[0]
  const waiting = phase.artefacts.filter((a) => a.waits_for.length > 0).length
  const names = Object.fromEntries(phase.artefacts.map((a) => [a.key, a.name]))
  const cardOf = (key: string) => screen.cards.find((c) => c.phase_key === phase.key && c.type === key) ?? null
  const rv = screen.review
  const statusOf = (artefactId: string) => rv.state?.statuses.find((s) => s.artefact_id === artefactId) ?? null
  const written = screen.cards.filter((c) => c.phase_key === phase.key && c.latest_version !== null)
  const nameById = { ...Object.fromEntries(written.map((c) => [c.id, c.title])), ...names }
  const open = rv.state?.open ?? null
  const openThings = open ? openCount(open) : 0
  const pending = rv.state?.artefacts_with_notes ?? []
  const specs = actionSpecs(phase, project.mode, openThings, pending.length)
  const reviewable = (phase.status === 'running' || phase.status === 'awaiting_review') && written.length > 0
  const sendBackRows = written.map((c) => ({ id: c.id, name: c.title, hasReview: statusOf(c.id)?.state === 'reviewed' || statusOf(c.id)?.state === 'stale' }))
  const press = (action: PhaseAction) => {
    const route = pressRoute(action, phase, pending.length)
    if (route === 'open_send_back') return rv.onStartSendBack()
    if (route === 'open_reopen') return rv.onStartReopen()
    if (route === 'rerun_notes') return rv.onRerunNotes()
    return screen.onAct(action)
  }
  const showingThisPhase = screen.progress.phase === phase.key
  return (
    <section>
      <a href="#/" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 no-underline hover:text-slate-900"><ArrowLeft size={14} aria-hidden /> Projects</a>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">{project.name}</h1>
        <ModeChip mode={project.mode} />
      </div>
      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <PhaseRail projectId={project.id} phases={project.phases} selected={phase.key} />
        <div className="min-w-0 space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-bold">{phase.name}</h2>
              <StatusPill status={phase.status} />
            </div>
            <p className="mt-1 text-sm text-slate-600">{project.next_action}</p>
            {phase.blocked_by && phase.status === 'not_started' && <div className="mt-3"><Notice tone="info">Waiting for {phase.blocked_by} to be approved first.</Notice></div>}
            {phase.feedback && <div className="mt-3"><Notice tone="warn" title="Sent back">{phase.feedback}</Notice></div>}
            {phase.status === 'approved' && phase.decided_by && <p className="mt-2 text-xs text-slate-500">Approved by {phase.decided_by.replace(/^human:/, '')}.</p>}
            <p className="mt-3 text-sm text-slate-700">
              {count(phase.artefacts.length, 'artefact')}{waiting > 0 ? ` · ${waiting} waiting on others` : ''} · approved by the {phase.approver}.
            </p>
            <ul className="mt-2 list-none space-y-2 p-0">
              {phase.artefacts.map((a) => (
                <ArtefactCardView key={a.key} name={a.name} card={cardOf(a.key)} selected={screen.open?.type === a.key} onOpen={screen.onOpen}
                  review={cardOf(a.key) && rv.state ? statusOf(cardOf(a.key)!.id) : undefined} />
              ))}
            </ul>

            {rv.state && rv.state.stale.length > 0 && phase.status !== 'approved' && (
              <div className="mt-3"><StaleBanner stale={rv.state.stale} names={nameById} busy={screen.busy !== null} canChange={canChange && !screen.runLive} onRerun={rv.onRerunStale} /></div>
            )}

            {reviewable && (
              <div className="mt-3 space-y-2">
                {rv.available ? (
                  <button type="button" onClick={rv.onReviewAll} disabled={rv.busy !== null || !canChange || screen.runLive}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold disabled:opacity-40">{rv.busy === 'phase' ? 'Reviewing…' : 'Review all'}</button>
                ) : rv.state?.replay_sentence ? <p className="text-xs text-slate-500">{rv.state.replay_sentence}</p> : null}
                {rv.available && !rv.run && <p className="text-xs text-slate-500">A second model reads each artefact and lists what it finds. This calls real models and costs money; it never happens by itself.</p>}
                {rv.run && <ReviewProgress run={rv.run} onStop={rv.onStopReviews} onDismiss={rv.onDismissReviews} />}
                {rv.error && <Notice tone="error" title="The review could not be run">{rv.error}</Notice>}
                {rv.paused && <FamilyPicker slot={rv.paused.slot} options={rv.paused.options} chosen={rv.chosenFamily} busy={rv.busy !== null} onChoose={rv.onChooseFamily} onReview={rv.onReviewWithChosen} />}
              </div>
            )}

            {open && (phase.status === 'awaiting_review' || phase.status === 'approved') && <div className="mt-3"><ApprovalSummary open={open} names={nameById} recorded={phase.status === 'approved'} /></div>}

            <div className="mt-4 flex flex-wrap items-start gap-3">
              {specs.length === 0
                ? <span className="text-sm text-slate-500">Nothing to do here right now.</span>
                : specs.map((s) => (
                    <div key={s.action} className="max-w-xs">
                      <button type="button" onClick={() => press(s.action)} disabled={!s.live || !canChange || screen.busy !== null || (screen.runLive && s.action !== 'run')}
                        className={`rounded-lg px-3 py-1.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${s.action === 'run' || s.action === 'approve' ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}>
                        {screen.busy === s.action ? `${s.label}…` : s.label}
                      </button>
                      <p className="mt-1 text-xs text-slate-500">{s.hint}</p>
                    </div>
                  ))}
            </div>
            {screen.actionError && <div className="mt-3"><Notice tone="error" title="That could not be done">{screen.actionError}</Notice></div>}

            {project.connectors.length > 0 && (
              <p className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
                Connectors noted: {project.connectors.map((c) => CONNECTOR_LABEL[c]).join(', ')} <SimulatedBadge />
              </p>
            )}
          </div>

          {showingThisPhase && (
            <RunPanel progress={screen.progress} names={names} connected={screen.connected} cancelling={screen.busy === 'cancel'} cancelNote={screen.cancelNote}
              problem={screen.streamProblem} onCancel={screen.onCancel} onOpen={screen.onOpen} />
          )}

          {rv.reopening && (
            <ReopenForm phaseName={phase.name} busy={rv.reopenBusy} error={rv.reopenError} laterStarted={laterStartedNames(project.phases, phase)}
              onReopen={rv.onReopen} onCancel={rv.onCancelReopen} />
          )}

          {rv.sendingBack && (
            <RequestChangesForm rows={sendBackRows} busy={rv.changesBusy} error={rv.changesError} onSend={rv.onSendBack} onCancel={rv.onCancelSendBack} />
          )}

          {screen.open && rv.editing && (
            <EditArtefact title={screen.open.title} initialBody={screen.open.body} busy={rv.editBusy} refusal={rv.editRefusal} error={rv.editError} onSave={rv.onSaveEdit} onCancel={rv.onCancelEdit} />
          )}

          {screen.open && !rv.editing && (
            <ArtefactReader artefact={screen.open} onClose={screen.onClose} onVersion={screen.onVersion}
              canReview={rv.available && reviewable && canChange} reviewBusy={rv.busy === screen.open.id} onReview={() => rv.onReviewOne(screen.open!.id)}
              reviewNote={!rv.available && reviewable ? rv.state?.replay_sentence ?? null : null}
              canEdit={(phase.status === 'running' || phase.status === 'awaiting_review') && canChange && !screen.runLive} onEdit={rv.onStartEdit} />
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <DocumentsPanel documents={screen.documents} busy={screen.busy === 'upload'} error={screen.uploadError} lastUpload={screen.lastUpload}
                onUpload={screen.onUpload} onPaste={screen.onPaste} onRemove={screen.onRemove} canChange={canChange} />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <SearchBox query={screen.query} onQuery={screen.onQuery} onSearch={screen.onSearch} searching={screen.searching} result={screen.result} error={screen.searchError} />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
