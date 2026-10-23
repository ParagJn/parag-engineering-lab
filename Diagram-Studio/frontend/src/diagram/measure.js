import { FONT } from './theme'

let context = null

function getContext() {
  if (!context) context = document.createElement('canvas').getContext('2d')
  return context
}

export function textWidth(text, size, family = FONT.sans, weight = 400) {
  if (!text) return 0
  const ctx = getContext()
  ctx.font = `${weight} ${size}px ${family}`
  return ctx.measureText(String(text)).width
}

// Everything sits on a 4px grid.
export const snap4 = (n) => Math.ceil(n / 4) * 4

/** Greedy word wrap by measured width. The last line gets an ellipsis if text is left over. */
export function wrapText(text, maxWidth, size, family = FONT.sans, weight = 400, maxLines = 4) {
  const words = String(text || '').split(/\s+/).filter(Boolean)
  const lines = []
  let line = ''
  for (const word of words) {
    const next = line ? `${line} ${word}` : word
    if (!line || textWidth(next, size, family, weight) <= maxWidth) {
      line = next
    } else {
      lines.push(line)
      line = word
    }
  }
  if (line) lines.push(line)
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines)
    kept[maxLines - 1] = kept[maxLines - 1].replace(/[\s.,;:]*$/, '') + '…'
    return kept
  }
  return lines
}

let fontsReady = null

/** Measure only after the web fonts are in, otherwise boxes are sized for the fallback font. */
export function ensureFonts() {
  if (!fontsReady) {
    if (!document.fonts || !document.fonts.load) {
      fontsReady = Promise.resolve()
    } else {
      fontsReady = Promise.all([
        document.fonts.load('500 13px Geist'),
        document.fonts.load('400 10.5px "Geist Mono"'),
        document.fonts.load('400 30px "Instrument Serif"'),
      ])
        .catch(() => {})
        .then(() => document.fonts.ready)
        .then(() => {})
    }
  }
  return fontsReady
}
