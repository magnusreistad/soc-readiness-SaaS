import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { NextRequest, NextResponse } from 'next/server'

const FASTAPI_URL = process.env.FASTAPI_URL ?? 'http://localhost:8000'

// Next.js has already decoded each segment once. Decode again so a
// double-encoded segment (%252e%252e -> %2e%2e, which fetch's URL parser
// treats as "..") is caught too. Malformed escapes are rejected outright.
function isSafeSegment(segment: string): boolean {
  let decoded: string
  try {
    decoded = decodeURIComponent(segment)
  } catch {
    return false
  }
  return ![segment, decoded].some(
    s => s === '.' || s === '..' || s.includes('/') || s.includes('\\')
  )
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const cookieStore = await cookies()

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() { return cookieStore.getAll() },
        setAll() {},
      },
    }
  )

  const { path } = await params
  // Reject before the public-path check, so "v1/auth/signup/../.." can't
  // match it and then normalise to a different route.
  if (!path.every(isSafeSegment)) {
    return NextResponse.json({ error: 'Invalid path' }, { status: 400 })
  }
  const targetPath = path.join('/')
  const PUBLIC_API_PATHS = ['v1/auth/signup']
  const isPublic = PUBLIC_API_PATHS.some(p => targetPath.startsWith(p))

  const { data: { session } } = await supabase.auth.getSession()
  if (!session && !isPublic) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // Re-encode the (already validated, decoded) segments so a "?" or "#"
  // inside one stays a path character instead of starting a query/fragment.
  const encodedPath = path.map(encodeURIComponent).join('/')
  const search = request.nextUrl.search
  const url = `${FASTAPI_URL}/api/${encodedPath}${search}`
  if (new URL(url).origin !== new URL(FASTAPI_URL).origin) {
    return NextResponse.json({ error: 'Invalid path' }, { status: 400 })
  }

  // Detect multipart — we must NOT override Content-Type for file uploads.
  // Multipart requests include a boundary in their Content-Type header that
  // the browser sets automatically. Overriding it breaks the upload.
  const incomingContentType = request.headers.get('content-type') ?? ''
  const isMultipart = incomingContentType.includes('multipart/form-data')

  const headers: Record<string, string> = {
    // Only inject Content-Type for JSON requests
    ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
    // Always forward auth if we have a session
    ...(session ? { 'Authorization': `Bearer ${session.access_token}` } : {}),
  }

  // For multipart, forward the original Content-Type (it contains the boundary)
  if (isMultipart) {
    headers['Content-Type'] = incomingContentType
  }

  let body: BodyInit | undefined
  if (['GET', 'HEAD'].includes(request.method)) {
    body = undefined
  } else if (isMultipart) {
    // Must use arrayBuffer for binary/multipart — text() mangles binary data
    body = await request.arrayBuffer()
  } else {
    body = await request.text()
  }

  const res = await fetch(url, {
    method: request.method,
    headers,
    body,
  })

  if (res.status === 204) {
    return new NextResponse(null, { status: 204 })
  }

  const data = await res.text()
  return new NextResponse(data, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export const GET    = handler
export const POST   = handler
export const PATCH  = handler
export const DELETE = handler