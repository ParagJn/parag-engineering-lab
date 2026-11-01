// Copy text to the clipboard. `navigator.clipboard` only exists on a secure page (https or localhost); anywhere else the old way, a hidden text
// box that is selected and copied, still works. Returns whether the text was copied, so the button can say so honestly and never claim "Copied" when it was not.

export interface ClipboardDeps {
  clipboard?: { writeText: (text: string) => Promise<void> } | null
  /** The old route. Receives the text and returns whether the browser copied it. */
  legacyCopy?: (text: string) => boolean
}

function legacyCopyFromPage(text: string): boolean {
  if (typeof document === 'undefined') return false
  const box = document.createElement('textarea')
  box.value = text
  box.setAttribute('readonly', '')
  box.style.position = 'fixed'
  box.style.opacity = '0'
  document.body.appendChild(box)
  box.select()
  try { return document.execCommand('copy') } catch { return false } finally { document.body.removeChild(box) }
}

export async function copyText(text: string, deps?: ClipboardDeps): Promise<boolean> {
  if (!text) return false
  const clipboard = deps && 'clipboard' in deps ? deps.clipboard : typeof navigator !== 'undefined' ? navigator.clipboard : null
  if (clipboard) {
    try { await clipboard.writeText(text); return true } catch { /* fall through to the old route */ }
  }
  return (deps?.legacyCopy ?? legacyCopyFromPage)(text)
}
