// What each action button says and does. WHICH buttons appear is decided by the server (`allowed_actions`); this only words them.
import type { PhaseAction, PhaseDetail } from '../api'

export interface ActionSpec {
  action: PhaseAction
  label: string
  /** One sentence under the button saying what it will do, and what it costs. */
  hint: string
  /** Every action is wired now (S12c); kept so a future action can be listed before it works. */
  live: boolean
}

/** `openThings` is how many things are still open (never reviewed, out of date, high findings...). Approving is never blocked by them, but the
 *  button says so: "Approve anyway". `rerunCount` is how many artefacts a re-run of a sent-back phase would rewrite (the server works it out). */
export function actionSpecs(phase: PhaseDetail, mode: 'replay' | 'live', openThings = 0, rerunCount = 0): ActionSpec[] {
  const words: Record<PhaseAction, Omit<ActionSpec, 'action'>> = {
    run: {
      label: phase.status === 'not_started' ? 'Run this phase' : phase.status === 'rejected' && rerunCount > 0 ? `Rewrite the ${rerunCount} sent back` : 'Run it again',
      hint: phase.status === 'rejected' && rerunCount > 0
        ? 'Rewrites only the artefacts you sent back, using your notes. The others are left as they are.'
        : mode === 'replay' ? 'Answers come from recordings: free and offline.' : 'Calls real models: this costs money.',
      live: true,
    },
    finish: { label: 'Hand to review', hint: 'Moves the phase to review. Nothing is written after this unless it is sent back.', live: true },
    approve: {
      label: openThings > 0 ? 'Approve anyway' : 'Approve',
      hint: openThings > 0 ? 'Records your approval, and what was still open, in the audit trail. Nothing stops you.' : 'Records your approval in the audit trail.',
      live: true,
    },
    reopen: { label: 'Reopen', hint: 'Takes this phase back to running so you can review, edit or rewrite it. You give a reason, which is recorded with your name. Phases after it are not changed.', live: true },
    request_changes: { label: 'Request changes', hint: 'Choose the artefacts to rewrite and say what is wrong with each.', live: true },
  }
  return phase.allowed_actions.map((action) => ({ action, ...words[action] }))
}

/** What pressing a phase button does on this screen. Three of them open a form or start a narrower run instead of acting at once. */
export type PressRoute = 'open_send_back' | 'open_reopen' | 'rerun_notes' | 'act'
export function pressRoute(action: PhaseAction, phase: Pick<PhaseDetail, 'status'>, pendingNotes: number): PressRoute {
  if (action === 'request_changes') return 'open_send_back'
  if (action === 'reopen') return 'open_reopen'
  if (action === 'run' && phase.status === 'rejected' && pendingNotes > 0) return 'rerun_notes'     // a plain run would rewrite nothing: every artefact already has a version
  return 'act'
}

/** Phase status shown beside the buttons when no run is going. */
export function isWritingNow(phase: PhaseDetail, runLive: boolean): boolean {
  return runLive && phase.status === 'running'
}
