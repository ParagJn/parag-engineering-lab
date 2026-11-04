// Small formatters. The rule that matters: money that is not known is "unknown", never $0.00.
export function money(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || !Number.isFinite(usd)) return 'unknown'
  if (usd === 0) return '$0.00'
  return usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(usd < 1 ? 4 : 2)}`
}

export function count(n: number, singular: string, plural = `${singular}s`): string {
  return `${n} ${n === 1 ? singular : plural}`
}

/** "2026-10-29T08:00:00.000Z" -> "29 Oct 2026". A value that is not a date is shown as given, never as "Invalid Date". */
export function shortDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export function seconds(s: number): string {
  if (!Number.isFinite(s) || s < 0) return 'unknown'
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`
  return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`
}

export const PHASE_STATUS_LABEL: Record<string, string> = {
  not_started: 'Not started', running: 'Running', awaiting_review: 'Awaiting review', approved: 'Approved', rejected: 'Sent back',
}

export const ACTION_LABEL: Record<string, string> = {
  run: 'Run this phase', finish: 'Hand to review', approve: 'Approve', request_changes: 'Request changes', reopen: 'Reopen',
}

export const CONNECTOR_LABEL: Record<string, string> = {
  source_control: 'Source control', issue_tracker: 'Issue tracker', ci_cd: 'CI/CD', cloud_account: 'Cloud account',
}

/** "agent:requirements_analyst@claude-sonnet-5-5" -> "requirements analyst · claude-sonnet-5-5"; "human:Ann" -> "Ann". Shown as text. */
export function authorLabel(author: string | null | undefined): string {
  if (!author) return 'unknown'
  if (author.startsWith('human:')) return author.slice('human:'.length) || 'a person'
  const rest = author.startsWith('agent:') ? author.slice('agent:'.length) : author
  const [role, model] = rest.split('@')
  return model ? `${role.replace(/_/g, ' ')} · ${model}` : role.replace(/_/g, ' ')
}

export function bytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return 'unknown'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export const ROW_STATE_LABEL: Record<string, string> = {
  waiting: 'Waiting', writing: 'Writing', retrying: 'Retrying', done: 'Done', failed: 'Failed', skipped: 'Skipped',
}

export const RUN_STATUS_LABEL: Record<string, string> = {
  idle: 'No run yet', running: 'Running', finished: 'Finished', stopped: 'Stopped early', failed: 'Finished with a failure', interrupted: 'Interrupted',
}

export const STOP_REASON_LABEL: Record<string, string> = {
  budget: 'the cost cap was reached', time: 'the time cap was reached', cancelled: 'you cancelled it',
}

export const RULE_LABEL: Record<string, string> = {
  email: 'an email address', phone: 'a phone number', payment_card: 'a payment card number', iban: 'a bank account number (IBAN)',
  private_key: 'a private key', configured_credential: 'a configured credential', aws_key_id: 'a cloud access key', github_token: 'a code-hosting token',
  slack_token: 'a chat token', stripe_key: 'a payment key', google_api_key: 'an API key', jwt: 'a sign-in token', url_password: 'a password in a web address',
  credential_assignment: 'a password or token assigned a value',
}

/** How independent a review was, in words a reader understands. The label is the system's, never the model's. */
export function independenceText(label: string, authorFamily: string, reviewerFamily: string): string {
  if (label === 'independent') return `Reviewed by ${reviewerFamily}, a different model family from the writer (${authorFamily}): independent`
  if (label === 'same_family') return `Reviewed by ${reviewerFamily}, the same model family as the writer: a second look, not an independent one`
  return 'The model families could not be compared, so independence is unverified'
}

export const INDEPENDENCE_SHORT: Record<string, string> = { independent: 'Independent', same_family: 'Same family', unverified: 'Unverified' }
export const SEVERITY_LABEL: Record<string, string> = { high: 'High', medium: 'Medium', low: 'Low' }
export const REVIEW_STATE_LABEL: Record<string, string> = { unreviewed: 'Not reviewed', reviewed: 'Reviewed', stale: 'Review out of date', retired: 'Retired' }

/** A price per million tokens, or "unknown". Never $0.00 for a price nobody told us. */
export function pricePerMillion(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || !Number.isFinite(usd)) return 'unknown'
  return `$${usd.toFixed(usd < 1 ? 2 : usd < 10 ? 2 : 0)}`
}

// ---- downloading the plan and the release notes (S21b) ------------------------------------------------------------------------------------

/** The artefacts that can be downloaded as a Markdown file and as a Word file. The server decides; this only says where to show the buttons. */
export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'] as const

export const isDownloadable = (type: string): boolean => (DOWNLOADABLE_TYPES as readonly string[]).includes(type)

/** The address of a file for one version of an artefact. The version is optional (the latest is sent when it is left out). */
export function downloadPath(projectId: string, artefactId: string, format: 'md' | 'docx', version?: number | null): string {
  const base = `/api/projects/${encodeURIComponent(projectId)}/artefacts/${encodeURIComponent(artefactId)}/download?format=${format}`
  return version ? `${base}&version=${version}` : base
}
