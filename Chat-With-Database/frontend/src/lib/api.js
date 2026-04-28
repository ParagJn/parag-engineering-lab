export class ApiError extends Error {
  constructor(payload, status = 0) {
    super(payload?.message || 'Request failed');
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

function normalizeErrorPayload(detail, fallbackMessage) {
  if (detail && typeof detail === 'object') {
    return {
      code: detail.code || 'request_failed',
      title: detail.title || 'Request failed',
      message: detail.message || fallbackMessage,
      suggestions: Array.isArray(detail.suggestions) ? detail.suggestions : [],
      issues: Array.isArray(detail.issues) ? detail.issues : [],
      technical_details: detail.technical_details || null,
    };
  }

  return {
    code: 'request_failed',
    title: 'Request failed',
    message: typeof detail === 'string' && detail ? detail : fallbackMessage,
    suggestions: [],
    issues: [],
    technical_details: null,
  };
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export async function apiRequest(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new ApiError({
      code: 'backend_unreachable',
      title: 'Backend API is unreachable',
      message: 'The frontend could not reach the backend service.',
      suggestions: [
        'Make sure the FastAPI backend is running on the expected host and port.',
        `If the backend runs elsewhere, set VITE_API_BASE_URL to the correct API origin instead of ${API_BASE_URL}.`,
        'Check local firewalls, VPN rules, or browser restrictions if the backend should already be reachable.',
      ],
      issues: [{ label: 'Network error', detail: error.message }],
      technical_details: error.message,
    });
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const payload = normalizeErrorPayload(data?.detail, 'The request could not be completed.');
    throw new ApiError(payload, response.status);
  }

  return data;
}