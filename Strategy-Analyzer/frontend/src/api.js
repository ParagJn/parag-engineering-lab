async function errorMessage(response, fallback) {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join('; ')
  } catch {
    // non-JSON error body
  }
  return `${fallback} (HTTP ${response.status})`
}

export async function uploadDocument(file, provider = 'ibm_ica') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('provider', provider)
  const response = await fetch('/api/upload', { method: 'POST', body: formData })
  if (!response.ok) throw new Error(await errorMessage(response, 'Upload failed'))
  return response.json()
}

export async function fetchProviders() {
  const response = await fetch('/api/providers')
  if (!response.ok) return {}
  return response.json()
}

export async function analyzeDocument(payload) {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await errorMessage(response, 'Analysis failed'))
  return response.json()
}

export async function askFollowUp(payload) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await errorMessage(response, 'Chat failed'))
  return response.json()
}

export async function createVisual(payload) {
  const response = await fetch('/api/visual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await errorMessage(response, 'Visual generation failed'))
  return response.json()
}

export function downloadMarkdown(markdown, filename = 'strategy-analysis.md') {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function downloadFromUrl(url, filename) {
  const response = await fetch(url)
  if (!response.ok) throw new Error('Download failed')
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.click()
  URL.revokeObjectURL(objectUrl)
}
