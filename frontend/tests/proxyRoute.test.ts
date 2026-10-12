// @vitest-environment node
import { NextRequest } from 'next/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('next/headers', () => ({
  cookies: async () => ({ getAll: () => [] }),
}))

vi.mock('@supabase/ssr', () => ({
  createServerClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: 'test-token' } } }),
    },
  }),
}))

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockResolvedValue(new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// The handler receives segments the way Next.js passes them: already
// URL-decoded once from the incoming request path.
async function callProxy(path: string[]) {
  const { GET } = await import('@/app/api/proxy/[...path]/route')
  const request = new NextRequest(`http://localhost/api/proxy/${path.join('/')}`)
  return GET(request, { params: Promise.resolve({ path }) })
}

describe('API proxy route', () => {
  it('forwards a normal path to the backend with the session token', async () => {
    const res = await callProxy(['v1', 'controls', '42'])

    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/v1/controls/42')
    expect(init.headers.Authorization).toBe('Bearer test-token')
  })

  it.each([
    // /api/proxy/v1/%2e%2e/%2e%2e/health -> Next decodes to ".."
    { name: 'encoded ../ segments', path: ['v1', '..', '..', 'health'] },
    // /api/proxy/v1/%252e%252e/health -> Next decodes to "%2e%2e"
    { name: 'double-encoded ../', path: ['v1', '%2e%2e', 'health'] },
    // /api/proxy/v1/..%2F..%2Fhealth -> slash inside a single segment
    { name: 'encoded slash', path: ['v1', '../../health'] },
    { name: 'backslash', path: ['v1', '..\\health'] },
    { name: 'single dot', path: ['v1', '.', 'controls'] },
    { name: 'malformed escape', path: ['v1', '%E0%A4%A'] },
    // Would otherwise match the public signup prefix and skip the session check
    { name: 'public-prefix traversal', path: ['v1', 'auth', 'signup', '..', '..', 'controls'] },
  ])('rejects $name without calling the backend', async ({ path }) => {
    const res = await callProxy(path)

    expect(res.status).toBe(400)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
