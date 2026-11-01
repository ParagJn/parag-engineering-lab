// "Who you are" is a label for the audit trail, not a login. It lives in this browser only, and the app works without storage.
export const ACTOR_KEY = 'sdlc-workbench.actor'
export const MAX_NAME = 60

export interface KeyValueStore { getItem(key: string): string | null; setItem(key: string, value: string): void }

export function cleanName(raw: string): string {
  return raw.replace(/[\u0000-\u001f\u007f]/g, ' ').split(/\s+/).filter(Boolean).join(' ')
}

/** Why a name cannot be used, in a sentence, or null if it is fine. The server checks again; this only saves a round trip. */
export function nameProblem(raw: string): string | null {
  const name = cleanName(raw)
  if (!name) return 'Enter a name to put in the audit trail.'
  if (name.length > MAX_NAME) return `Use ${MAX_NAME} characters or fewer.`
  if (/^(system|human:|agent:)/i.test(name)) return 'That name is reserved.'
  return null
}

export function loadName(store: KeyValueStore | null): string {
  try {
    return cleanName(store?.getItem(ACTOR_KEY) ?? '')
  } catch {
    return ''
  }
}

/** Returns false (and never throws) if storage is unavailable, so a private window still works for the session. */
export function saveName(store: KeyValueStore | null, raw: string): boolean {
  try {
    if (!store || nameProblem(raw)) return false
    store.setItem(ACTOR_KEY, cleanName(raw))
    return true
  } catch {
    return false
  }
}

export function browserStore(): KeyValueStore | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}
