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

export async function fetchStatus() {
  try {
    const response = await fetch('/api/status')
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function compareFiles(fileA, fileB, signal) {
  const formData = new FormData()
  formData.append('file_a', fileA)
  formData.append('file_b', fileB)
  const response = await fetch('/api/compare', { method: 'POST', body: formData, signal })
  if (!response.ok) throw new Error(await errorMessage(response, 'Comparison failed'))
  return response.json()
}

export function downloadMarkdown(markdown, filename) {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

async function json(response, fallback) {
  if (!response.ok) throw new Error(await errorMessage(response, fallback))
  return response.json()
}

export async function listComparisons(query = '') {
  const params = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''
  return (await json(await fetch(`/api/comparisons${params}`), 'Could not load history')).items
}

export async function getComparison(id) {
  return json(await fetch(`/api/comparisons/${id}`), 'Could not open comparison')
}

export async function getDiff(id) {
  return json(await fetch(`/api/comparisons/${id}/diff`), 'Could not build the diff')
}

export async function renameComparison(id, title) {
  return json(
    await fetch(`/api/comparisons/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }),
    'Rename failed',
  )
}

export async function deleteComparison(id) {
  return json(await fetch(`/api/comparisons/${id}`, { method: 'DELETE' }), 'Delete failed')
}
