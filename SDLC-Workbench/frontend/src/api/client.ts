// The only place the screen talks to the backend. Every response is decoded before it is used, and every failure becomes one of
// three plain things a person can act on: the backend is not running, the server said no (in its own words), or the two disagree.
import { ContractError, type Json } from './decode'
import { decodeTraceItem, decodeTraceability, type TraceItem, type Traceability } from './trace'
import { decodeChecklist, type Answer, type Checklist } from './deploy'
import { decodeVerifyDetail, decodeVerifyList, type VerifyDetail, type VerifyList } from './verify'
import { decodeChangesRequested, decodeEditFileSaved, decodeEditRefusal, decodeEditSaved, decodePhaseReview, decodeReviewAnswer, decodeReviewState, decodeRerun, type ChangesRequested, type EditFileSaved, type EditSaved, type RerunStarted, type ReviewAnswer, type ReviewState_ } from './review'
import {
  decodeCatalogue, decodeError, decodeMode, decodePlan, decodeProject, decodeProjectList, decodeStatus,
  type Catalogue, type ModeInfo, type Plan, type ProjectDetail, type ProjectSummary, type StatusSummary,
} from './types'
import {
  decodeArtefactDetail, decodeArtefactList, decodeCancel, decodeDocuments, decodeGate, decodeRemoved, decodeRun, decodeRunStarted, decodeRuns,
  decodeSample, decodeSearch, decodeUpload,
  type ArtefactCard, type ArtefactDetail, type CancelAnswer, type DocumentInfo, type GateAnswer, type RunRecord, type RunStarted, type Sample,
  type SearchResult, type UploadResult,
} from './content'

export class BackendUnreachable extends Error {
  constructor() {
    super('The backend is not reachable. Start it with ./start.sh (it listens on port 8090), then reload this page.')
    this.name = 'BackendUnreachable'
  }
}

/** The server refused the request, and said why. `message` is the server's own sentence and is shown as plain text. */
export class ServerRefused extends Error {
  /** `problems` is set when the server gave a LIST of reasons (a refused edit): each one is shown, and the text the person typed is kept. */
  constructor(public status: number, message: string, public problems: string[] = []) {
    super(message)
    this.name = 'ServerRefused'
  }
}

export type Fetcher = typeof fetch

export interface Client {
  status(): Promise<StatusSummary>
  mode(): Promise<ModeInfo>
  catalogue(): Promise<Catalogue>
  previewPlan(selection: Selection): Promise<Plan>
  listProjects(options?: { archived?: boolean }): Promise<ProjectSummary[]>
  archiveProject(id: string, actorName: string): Promise<ProjectDetail>
  restoreProject(id: string, actorName: string): Promise<ProjectDetail>
  getProject(id: string): Promise<ProjectDetail>
  createProject(input: NewProject, actorName: string): Promise<ProjectDetail>
  // S12b
  sample(): Promise<Sample>
  listDocuments(projectId: string): Promise<DocumentInfo[]>
  uploadDocument(projectId: string, file: File | Blob, filename: string, actorName: string): Promise<UploadResult>
  removeDocument(projectId: string, number: number, actorName: string): Promise<number>
  search(projectId: string, query: string): Promise<SearchResult>
  listArtefacts(projectId: string, phase?: string): Promise<ArtefactCard[]>
  getArtefact(projectId: string, artefactId: string, version?: number): Promise<ArtefactDetail>
  startRun(projectId: string, phase: string, actorName: string, options?: RunOptions): Promise<RunStarted>
  cancelRun(projectId: string, runId: string, actorName: string): Promise<CancelAnswer>
  getRun(projectId: string, runId: string): Promise<RunRecord>
  listRuns(projectId: string, phase?: string): Promise<RunRecord[]>
  finishPhase(projectId: string, phase: string, actorName: string): Promise<GateAnswer>
  approvePhase(projectId: string, phase: string, actorName: string): Promise<GateAnswer>
  reopenPhase(projectId: string, phase: string, actorName: string, reason: string): Promise<GateAnswer>
  // S12c
  reviewArtefact(projectId: string, artefactId: string, actorName: string, choice?: { slot?: string; exclude?: string[] }): Promise<ReviewAnswer>
  reviewPhase(projectId: string, phase: string, actorName: string): Promise<ReviewAnswer[]>
  reviewState(projectId: string, phase: string): Promise<ReviewState_>
  traceability(projectId: string): Promise<Traceability>
  traceItem(projectId: string, itemId: string): Promise<TraceItem>
  /** S20: Build Verify. Compare the real build, in folders on this computer, with the design. */
  verifyRuns(projectId: string): Promise<VerifyList>
  /** S21c: the deployment checklist. Reading needs no name; answering a check is saved in the person's name. */
  checklist(projectId: string, phase?: string): Promise<Checklist>
  answerCheck(projectId: string, checkId: string, actorName: string, answer: Answer, note: string, phase?: string): Promise<Checklist>
  verifyRun(projectId: string, runId: number): Promise<VerifyDetail>
  runVerify(projectId: string, actorName: string, backendPath: string, frontendPath: string | null): Promise<VerifyDetail>
  requestChanges(projectId: string, phase: string, actorName: string, input: ChangeRequest): Promise<ChangesRequested>
  rerun(projectId: string, phase: string, actorName: string): Promise<RerunStarted>
  rerunStale(projectId: string, phase: string, actorName: string): Promise<RerunStarted>
  editArtefact(projectId: string, artefactId: string, actorName: string, body: string, note: string): Promise<EditSaved>
  /** S19f: change ONE file of the Build instruction set. `basedOn` is the version the person was looking at; the server refuses if the set has moved on. */
  editFile(projectId: string, artefactId: string, fileName: string, actorName: string, text: string, note: string, basedOn: number): Promise<EditFileSaved>
}

/** What to send back: a note per artefact (required), an optional note for the whole phase, and which artefacts also pass on the reviewer's findings. */
export interface ChangeRequest { notes: Record<string, string>; overall?: string; include_findings?: string[] }

export interface RunOptions { only?: string[]; rewrite_all?: boolean; review?: boolean }

/** phase key -> artefact keys switched ON (a phase left out gets everything). Exactly what the server's plan builder takes. */
export type Selection = Record<string, string[]>
export interface NewProject { name: string; brief: string; selection: Selection; connectors: string[] }

export function makeClient(fetcher: Fetcher = (...args) => fetch(...args), base = ''): Client {
  async function call(path: string, init?: RequestInit): Promise<unknown> {
    let response: Response
    try {
      response = await fetcher(base + path, init)
    } catch {
      throw new BackendUnreachable()
    }
    let body: unknown
    try {
      body = await response.json()
    } catch {
      if (!response.ok) throw new ServerRefused(response.status, `The backend returned an error (${response.status}) with no explanation.`)
      throw new ContractError(path, 'the reply was not JSON')
    }
    if (!response.ok) {
      const refusal = decodeEditRefusal(body)
      if (refusal) throw new ServerRefused(response.status, refusal.message, refusal.problems)
      throw new ServerRefused(response.status, decodeError(body))
    }
    return body
  }

  const post = (path: string, payload: Json, headers: Record<string, string> = {}) =>
    call(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(payload) })
  const id = encodeURIComponent
  const who = (actorName: string) => ({ 'X-Actor': actorName })

  return {
    status: async () => decodeStatus(await call('/api/status')),
    mode: async () => decodeMode(await call('/api/modes')),
    catalogue: async () => decodeCatalogue(await call('/api/catalogue')),
    previewPlan: async (selection) => decodePlan(await post('/api/plan/preview', { selection })),
    listProjects: async (options = {}) => decodeProjectList(await call(options.archived ? '/api/projects?archived=true' : '/api/projects')),
    archiveProject: async (projectId, actorName) => decodeProject(await call(`/api/projects/${encodeURIComponent(projectId)}/archive`, { method: 'POST', headers: { 'X-Actor': actorName } })),
    restoreProject: async (projectId, actorName) => decodeProject(await call(`/api/projects/${encodeURIComponent(projectId)}/restore`, { method: 'POST', headers: { 'X-Actor': actorName } })),
    getProject: async (id) => decodeProject(await call(`/api/projects/${encodeURIComponent(id)}`)),
    createProject: async (input, actorName) =>
      decodeProject(await post('/api/projects', { ...input }, { 'X-Actor': actorName })),

    traceability: async (projectId) => decodeTraceability(await call(`/api/projects/${id(projectId)}/traceability`)),
    checklist: async (projectId, phase = 'deploy') => decodeChecklist(await call(`/api/projects/${id(projectId)}/${id(phase)}/checklist`)),
    answerCheck: async (projectId, checkId, actorName, answer, note, phase = 'deploy') =>
      decodeChecklist(await call(`/api/projects/${id(projectId)}/${id(phase)}/checklist/${id(checkId)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ answer, note }),
      })),
    verifyRuns: async (projectId) => decodeVerifyList(await call(`/api/projects/${id(projectId)}/verify`)),
    verifyRun: async (projectId, runId) => decodeVerifyDetail(await call(`/api/projects/${id(projectId)}/verify/${id(String(runId))}`)),
    runVerify: async (projectId, actorName, backendPath, frontendPath) =>
      decodeVerifyDetail(await call(`/api/projects/${id(projectId)}/verify`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ backend_path: backendPath, frontend_path: frontendPath }),
      })),
    traceItem: async (projectId, itemId) => decodeTraceItem(await call(`/api/projects/${id(projectId)}/traceability/item/${id(itemId)}`)),

    sample: async () => decodeSample(await call('/api/sample')),
    listDocuments: async (projectId) => decodeDocuments(await call(`/api/projects/${id(projectId)}/documents`)),
    uploadDocument: async (projectId, file, filename, actorName) => {
      const form = new FormData()
      form.append('file', file, filename)     // no Content-Type: the browser sets the multipart boundary itself
      return decodeUpload(await call(`/api/projects/${id(projectId)}/documents`, { method: 'POST', headers: who(actorName), body: form }))
    },
    removeDocument: async (projectId, number, actorName) =>
      decodeRemoved(await call(`/api/projects/${id(projectId)}/documents/${number}`, { method: 'DELETE', headers: who(actorName) })),
    search: async (projectId, query) => decodeSearch(await call(`/api/projects/${id(projectId)}/search?q=${encodeURIComponent(query)}`)),
    listArtefacts: async (projectId, phase) =>
      decodeArtefactList(await call(`/api/projects/${id(projectId)}/artefacts${phase ? `?phase=${encodeURIComponent(phase)}` : ''}`)),
    getArtefact: async (projectId, artefactId, version) =>
      decodeArtefactDetail(await call(`/api/projects/${id(projectId)}/artefacts/${id(artefactId)}${version ? `?version=${version}` : ''}`)),
    startRun: async (projectId, phase, actorName, options = {}) =>
      decodeRunStarted(await post(`/api/projects/${id(projectId)}/phases/${id(phase)}/run`, { ...options }, who(actorName))),
    cancelRun: async (projectId, runId, actorName) =>
      decodeCancel(await call(`/api/projects/${id(projectId)}/runs/${id(runId)}/cancel`, { method: 'POST', headers: who(actorName) })),
    getRun: async (projectId, runId) => decodeRun(await call(`/api/projects/${id(projectId)}/runs/${id(runId)}`)),
    listRuns: async (projectId, phase) => decodeRuns(await call(`/api/projects/${id(projectId)}/runs${phase ? `?phase=${encodeURIComponent(phase)}` : ''}`)),
    finishPhase: async (projectId, phase, actorName) =>
      decodeGate(await call(`/api/projects/${id(projectId)}/phases/${id(phase)}/finish`, { method: 'POST', headers: who(actorName) })),
    approvePhase: async (projectId, phase, actorName) =>
      decodeGate(await call(`/api/projects/${id(projectId)}/phases/${id(phase)}/approve`, { method: 'POST', headers: who(actorName) })),

    reopenPhase: async (projectId, phase, actorName, reason) =>
      decodeGate(await post(`/api/projects/${id(projectId)}/phases/${id(phase)}/reopen`, { reason }, who(actorName))),
    reviewArtefact: async (projectId, artefactId, actorName, choice = {}) =>
      decodeReviewAnswer(await post(`/api/projects/${id(projectId)}/artefacts/${id(artefactId)}/review`, { ...choice }, who(actorName))),
    reviewPhase: async (projectId, phase, actorName) =>
      decodePhaseReview(await post(`/api/projects/${id(projectId)}/phases/${id(phase)}/review`, {}, who(actorName))),
    reviewState: async (projectId, phase) => decodeReviewState(await call(`/api/projects/${id(projectId)}/phases/${id(phase)}/review`)),
    requestChanges: async (projectId, phase, actorName, input) =>
      decodeChangesRequested(await post(`/api/projects/${id(projectId)}/phases/${id(phase)}/request-changes`, { ...input }, who(actorName))),
    rerun: async (projectId, phase, actorName) => decodeRerun(await call(`/api/projects/${id(projectId)}/phases/${id(phase)}/rerun`, { method: 'POST', headers: who(actorName) })),
    rerunStale: async (projectId, phase, actorName) =>
      decodeRerun(await call(`/api/projects/${id(projectId)}/phases/${id(phase)}/rerun-stale`, { method: 'POST', headers: who(actorName) })),
    editArtefact: async (projectId, artefactId, actorName, body, note) =>
      decodeEditSaved(await call(`/api/projects/${id(projectId)}/artefacts/${id(artefactId)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ body, note }),
      })),
    editFile: async (projectId, artefactId, fileName, actorName, text, note, basedOn) =>
      decodeEditFileSaved(await call(`/api/projects/${id(projectId)}/artefacts/${id(artefactId)}/files/${encodeURIComponent(fileName)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ text, note, based_on: basedOn }),
      })),
  }
}
