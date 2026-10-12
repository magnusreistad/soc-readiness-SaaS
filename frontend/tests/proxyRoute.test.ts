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
// URL-decoded once from the incoming request path. The request URL itself
// carries them encoded, as a browser would send them.
async function callProxy(path: string[], search = '') {
  const { GET } = await import('@/app/api/proxy/[...path]/route')
  const encoded = path.map(encodeURIComponent).join('/')
  const request = new NextRequest(`http://localhost/api/proxy/${encoded}${search}`)
  return GET(request, { params: Promise.resolve({ path }) })
}

function fetchedUrl(): string {
  expect(fetchMock).toHaveBeenCalledOnce()
  return fetchMock.mock.calls[0][0]
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

  it('leaves a multi-segment path with IDs unchanged', async () => {
    await callProxy(['v1', 'controls', '42', 'evidence', '17', 're-evaluate'])

    expect(fetchedUrl()).toBe('http://localhost:8000/api/v1/controls/42/evidence/17/re-evaluate')
  })

  it('forwards the real query string untouched', async () => {
    await callProxy(['v1', 'incidents'], '?status=new&limit=50')

    expect(fetchedUrl()).toBe('http://localhost:8000/api/v1/incidents?status=new&limit=50')
  })

  it('encodes "?" inside a segment as a path character, not a query string', async () => {
    // /api/proxy/v1/vendors/7%3Fadmin%3Dtrue -> Next decodes to "7?admin=true"
    await callProxy(['v1', 'vendors', '7?admin=true'])

    const url = fetchedUrl()
    expect(url).toBe('http://localhost:8000/api/v1/vendors/7%3Fadmin%3Dtrue')
    expect(new URL(url).search).toBe('')
  })

  it('encodes "#" inside a segment as a path character, not a fragment', async () => {
    // /api/proxy/v1/vendors/7%23frag -> Next decodes to "7#frag"
    await callProxy(['v1', 'vendors', '7#frag', 'notes'])

    const url = fetchedUrl()
    expect(url).toBe('http://localhost:8000/api/v1/vendors/7%23frag/notes')
    expect(new URL(url).hash).toBe('')
    expect(new URL(url).pathname).toBe('/api/v1/vendors/7%23frag/notes')
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
