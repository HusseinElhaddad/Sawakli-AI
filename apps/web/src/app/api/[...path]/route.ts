import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

type RouteContext = {
  params: Promise<{ path: string[] }>
}

function apiBaseUrl(): string {
  return (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
}

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params
  const target = new URL(`${apiBaseUrl()}/api/${path.join('/')}`)
  target.search = new URL(request.url).search

  const headers = new Headers()
  const authorization = request.headers.get('authorization')
  const contentType = request.headers.get('content-type')
  if (authorization) headers.set('authorization', authorization)
  if (contentType) headers.set('content-type', contentType)

  try {
    const requestBody = request.method === 'GET' || request.method === 'HEAD'
      ? undefined
      : await request.arrayBuffer()

    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: requestBody,
      cache: 'no-store',
    })

    const responseHeaders = new Headers()
    const responseContentType = upstream.headers.get('content-type')
    if (responseContentType) responseHeaders.set('content-type', responseContentType)

    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    })
  } catch {
    return NextResponse.json(
      { detail: { code: 'api_unavailable', message: 'The Sawakli service is unavailable. Please try again.', retryable: true } },
      { status: 503 },
    )
  }
}

export const GET = proxy
export const POST = proxy
