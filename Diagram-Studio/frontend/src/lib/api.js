async function parse(response) {
  let body = null
  try {
    body = await response.json()
  } catch {
    // not JSON: fall through to the generic message
  }
  if (!response.ok) {
    const detail = body && body.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : null
    throw new Error(message || `Request failed (${response.status}).`)
  }
  return body
}

async function request(url, options) {
  try {
    return await parse(await fetch(url, options))
  } catch (err) {
    if (err instanceof TypeError) throw new Error('Could not reach the backend. Is Diagram Studio running?')
    throw err
  }
}

export const getStatus = () => request('/api/status')

export function planDiagrams({ file, text }) {
  const form = new FormData()
  if (file) form.append('file', file)
  else form.append('text', text)
  return request('/api/plan', { method: 'POST', body: form })
}

export function drawDiagram({ text, item, instruction = '', projectId = '' }) {
  return request('/api/diagram', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, item, instruction, project_id: projectId || '' }),
  })
}

export function createAnimation({ type, title, instruction = '', elements = [] }) {
  return request('/api/animation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, title, instruction, elements }),
  })
}

export const listProjects = (q = '') => request(`/api/projects?q=${encodeURIComponent(q)}`)
export const getProject = (id) => request(`/api/projects/${encodeURIComponent(id)}`)
export const deleteProject = (id) => request(`/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const renameProject = (id, title) =>
  request(`/api/projects/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
