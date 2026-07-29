// lib/api.ts
// Central API client — proxies all requests through /api/proxy/v1/
// which injects the Supabase Bearer token server-side.

async function apiFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`/api/proxy/v1/${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (!res.ok) {
    const error = await res.text()
    throw new Error(`API error ${res.status}: ${error}`)
  }
  return res.json()
}

// For multipart file uploads — do NOT set Content-Type.
// The browser sets it automatically with the correct boundary.
async function apiUpload(path: string, formData: FormData) {
  const res = await fetch(`/api/proxy/v1/${path}`, {
    method: 'POST',
    body: formData,
    // No Content-Type header — browser sets multipart/form-data with boundary
  })
  if (!res.ok) {
    const error = await res.text()
    // Try to parse as JSON for structured error detail from FastAPI
    try {
      const parsed = JSON.parse(error)
      throw new Error(parsed.detail ?? `API error ${res.status}`)
    } catch {
      throw new Error(`API error ${res.status}: ${error}`)
    }
  }
  return res.json()
}

export const api = {
  get: (path: string) =>
    apiFetch(path),

  post: (path: string, body: unknown) =>
    apiFetch(path, { method: 'POST', body: JSON.stringify(body) }),

  patch: (path: string, body: unknown) =>
    apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) }),

  delete: async (path: string) => {
    const res = await fetch(`/api/proxy/v1/${path}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) {
      const error = await res.text()
      throw new Error(`API error ${res.status}: ${error}`)
    }
    return res.status === 204 ? null : res.json()
  },

  // Multipart file upload — used by the evidence uploader
  upload: (path: string, formData: FormData) =>
    apiUpload(path, formData),
}