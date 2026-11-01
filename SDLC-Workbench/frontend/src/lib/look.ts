// Which look a diagram is shown in. A per-viewer convenience: remembered in the browser, never required, and always safe to lose.

export const LOOKS = ['drawio', 'notion'] as const
export type Look = (typeof LOOKS)[number]
export const DEFAULT_LOOK: Look = 'drawio'
export const LOOK_LABEL: Record<Look, string> = { drawio: 'draw.io', notion: 'Notion' }
export const LOOK_KEY = 'sdlc.diagram.look'

export interface LookStore { getItem(key: string): string | null; setItem(key: string, value: string): void }

export const isLook = (value: unknown): value is Look => typeof value === 'string' && (LOOKS as readonly string[]).includes(value)

/** The remembered look, or the default when there is none, it is not one of ours, or the browser will not say. */
export function readLook(store: LookStore | null): Look {
  try {
    const saved = store?.getItem(LOOK_KEY)
    return isLook(saved) ? saved : DEFAULT_LOOK
  } catch {
    return DEFAULT_LOOK
  }
}

/** Remember a look. Returns whether it was saved; a browser that refuses is not an error. */
export function saveLook(store: LookStore | null, look: Look): boolean {
  try {
    if (!store || !isLook(look)) return false
    store.setItem(LOOK_KEY, look)
    return true
  } catch {
    return false
  }
}

/** The picture to show: the one for the chosen look, else the default look's, else any one, else nothing. */
export function pictureFor(renderings: Readonly<Record<string, string>> | null, look: Look): string | null {
  if (!renderings) return null
  return renderings[look] ?? renderings[DEFAULT_LOOK] ?? Object.values(renderings)[0] ?? null
}

/** The look to start in: the one asked for, else the remembered one, else the default. */
export function startLook(asked: Look | undefined, store: LookStore | null): Look {
  return asked !== undefined && isLook(asked) ? asked : readLook(store)
}

/** The person chose a look: remember it, and return it. */
export function chooseLook(store: LookStore | null, next: Look): Look {
  saveLook(store, next)
  return next
}
