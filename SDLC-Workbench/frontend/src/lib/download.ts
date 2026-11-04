// Save text as a file on the person's own machine. Nothing is sent anywhere: the browser makes a file from text that is already on the page.
export function saveText(filename: string, text: string): void {
  saveBlob(filename, new Blob([text], { type: 'text/plain;charset=utf-8' }))
}

/** Save bytes (a zip) as a file on the person's own machine. */
export function saveBytes(filename: string, bytes: Uint8Array, type = 'application/zip'): void {
  saveBlob(filename, new Blob([bytes as BlobPart], { type }))
}

function saveBlob(filename: string, blob: Blob): void {
  if (typeof document === 'undefined') return
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
