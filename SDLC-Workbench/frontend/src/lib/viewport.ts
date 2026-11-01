// The arithmetic behind zoom, pan and fit for a picture. Pure functions, no DOM, so every rule can be tested without a browser.
//
// A view is where the picture's top-left corner sits inside its frame (x, y, in frame pixels) and how big it is drawn (scale, 1 = natural size).

export interface View { scale: number; x: number; y: number }
export interface Size { width: number; height: number }

export const MIN_SCALE = 0.1
export const MAX_SCALE = 8
export const STEP = 1.25

export const clampScale = (scale: number): number => (Number.isFinite(scale) ? Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale)) : 1)

/** The view that shows the whole picture inside the frame, centred, never enlarged past natural size unless `enlarge` is set. */
export function fit(frame: Size, content: Size, margin = 16, enlarge = false): View {
  if (frame.width <= 0 || frame.height <= 0 || content.width <= 0 || content.height <= 0) return { scale: 1, x: 0, y: 0 }
  const raw = Math.min((frame.width - 2 * margin) / content.width, (frame.height - 2 * margin) / content.height)
  const scale = clampScale(enlarge ? raw : Math.min(1, raw))
  return { scale, x: (frame.width - content.width * scale) / 2, y: (frame.height - content.height * scale) / 2 }
}

/** Change the scale but keep the point of the picture under (px, py), in frame pixels, exactly where it is: zoom towards the pointer. */
export function zoomAt(view: View, factor: number, px: number, py: number): View {
  const scale = clampScale(view.scale * factor)
  const ratio = scale / view.scale
  return { scale, x: px - (px - view.x) * ratio, y: py - (py - view.y) * ratio }
}

export const pan = (view: View, dx: number, dy: number): View => ({ ...view, x: view.x + dx, y: view.y + dy })

/** Keep at least `keep` pixels of the picture inside the frame, so it can never be dragged out of reach. */
export function keepReachable(view: View, frame: Size, content: Size, keep = 48): View {
  const w = content.width * view.scale
  const h = content.height * view.scale
  return {
    scale: view.scale,
    x: Math.min(frame.width - keep, Math.max(keep - w, view.x)),
    y: Math.min(frame.height - keep, Math.max(keep - h, view.y)),
  }
}

/** A wheel turn as a zoom factor: one notch is one step, however fast the wheel reports it. */
export const wheelFactor = (deltaY: number): number => (deltaY === 0 || !Number.isFinite(deltaY) ? 1 : deltaY < 0 ? STEP : 1 / STEP)

export const percent = (view: View): string => `${Math.round(view.scale * 100)}%`

/** The natural size of a picture, from the width and height or viewBox it declares. */
export function sizeOf(svg: string): Size | null {
  const box = /viewBox="\s*[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)\s+([0-9.]+)\s*"/.exec(svg)
  if (!box) return null
  const width = Number(box[1])
  const height = Number(box[2])
  return width > 0 && height > 0 ? { width, height } : null
}

// ---- what each key and control does, as plain functions so every one can be tested without a browser ----------------------------------------------

export type Command = { kind: 'zoom'; factor: number } | { kind: 'move'; dx: number; dy: number } | { kind: 'fit' }

/** What a key does to the picture, or null for a key that is not ours (which is then left alone, so Tab and the rest keep working). */
export function commandForKey(key: string, step = 40): Command | null {
  switch (key) {
    case '+': case '=': return { kind: 'zoom', factor: STEP }
    case '-': return { kind: 'zoom', factor: 1 / STEP }
    case '0': return { kind: 'fit' }
    case 'ArrowLeft': return { kind: 'move', dx: step, dy: 0 }          // the picture moves with the arrow: left shows more of what is on the left
    case 'ArrowRight': return { kind: 'move', dx: -step, dy: 0 }
    case 'ArrowUp': return { kind: 'move', dx: 0, dy: step }
    case 'ArrowDown': return { kind: 'move', dx: 0, dy: -step }
    default: return null
  }
}

/** The view after a command. A fit is worked out from the frame and the picture; the rest are kept within reach. */
export function apply(command: Command, view: View, frame: Size, content: Size, enlarge = false): View {
  if (command.kind === 'fit') return fit(frame, content, 16, enlarge)
  if (command.kind === 'move') return keepReachable(pan(view, command.dx, command.dy), frame, content)
  return keepReachable(zoomAt(view, command.factor, frame.width / 2, frame.height / 2), frame, content)
}

/** Does a key press close full screen? */
export const closesFullScreen = (key: string): boolean => key === 'Escape'

/** What the page behind does while a picture is full screen: it must not scroll, and it gets its own setting back afterwards. */
export interface PageScroll { lock(): () => void }
export function pageScroll(style: { overflow: string }): PageScroll {
  return { lock() { const before = style.overflow; style.overflow = 'hidden'; return () => { style.overflow = before } } }
}

/** What each button on the viewer does. The component draws a button for each and runs the command, so the wiring is here, where a test can read it. */
export type ButtonName = 'zoomIn' | 'zoomOut' | 'fit' | 'full'
export const BUTTON_COMMAND: Record<ButtonName, Command | 'full'> = {
  zoomIn: { kind: 'zoom', factor: STEP },
  zoomOut: { kind: 'zoom', factor: 1 / STEP },
  fit: { kind: 'fit' },
  full: 'full',
}
