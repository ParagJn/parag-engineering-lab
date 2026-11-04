// Follows a project's run events. The browser's EventSource reconnects on its own and re-sends the last id it saw (Last-Event-ID), so
// a dropped connection loses nothing; the reducer ignores an event it has already applied, so a repeat changes nothing either.
import type { RunEvent } from './events'
import { parseFrame } from './events'

/** The small part of EventSource this code uses, so a test can supply a fake with no browser. */
export interface SourceLike {
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null
  onerror: ((e: unknown) => void) | null
  addEventListener(type: string, listener: (e: { data: string; lastEventId: string }) => void): void
  close(): void
}
export type SourceFactory = (url: string) => SourceLike

export interface Follow { close(): void }
export interface FollowHandlers {
  onEvent(event: RunEvent): void
  /** The server dropped this watcher for being too slow. Re-open to catch up; nothing was lost. */
  onDropped(): void
  onProblem(message: string): void
  onConnectionChange?(connected: boolean): void
}

export const STREAM_EVENT_NAMES = [
  'run.started', 'gate.changed', 'artefact.started', 'artefact.attempt', 'artefact.finished', 'artefact.failed', 'artefact.skipped', 'build.round',
  'piece.started', 'piece.finished', 'piece.failed', 'review.started', 'review.finished', 'review.paused', 'run.finished', 'run.stopped', 'dropped',
] as const

export function followEvents(
  projectId: string, afterId: number, handlers: FollowHandlers,
  make: SourceFactory = (url) => new EventSource(url) as unknown as SourceLike,
): Follow {
  const source = make(`/api/projects/${encodeURIComponent(projectId)}/events?after=${Math.max(0, Math.floor(afterId))}`)
  let open = true
  const deliver = (name: string, e: { data: string; lastEventId: string }) => {
    if (!open) return
    try {
      const parsed = parseFrame(`id: ${e.lastEventId}\nevent: ${name}\ndata: ${e.data}`)
      if (parsed === null) return
      if ('dropped' in parsed) { handlers.onDropped(); return }
      handlers.onConnectionChange?.(true)
      handlers.onEvent(parsed)
    } catch (error) {
      handlers.onProblem(error instanceof Error ? error.message : 'An event could not be read.')
    }
  }
  for (const name of STREAM_EVENT_NAMES) source.addEventListener(name, (e) => deliver(name, e))
  source.onerror = () => handlers.onConnectionChange?.(false)    // the browser retries by itself; this only says "not connected right now"
  return { close() { open = false; source.close() } }
}
