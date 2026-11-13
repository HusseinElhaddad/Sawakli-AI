export type ApiProblem = {
  code?: string
  message?: string
  retryable?: boolean
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly retryable: boolean

  constructor(message: string, status: number, problem?: ApiProblem) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = problem?.code
    this.retryable = problem?.retryable ?? status >= 500
  }
}

type ApiRequestOptions = Omit<RequestInit, 'body' | 'headers'> & {
  accessToken?: string
  body?: BodyInit | null
  headers?: HeadersInit
}

function isProblem(value: unknown): value is ApiProblem {
  return typeof value === 'object' && value !== null
}

async function readProblem(response: Response): Promise<ApiProblem | undefined> {
  const body: unknown = await response.json().catch(() => undefined)
  if (!isProblem(body) || !('detail' in body)) return undefined

  const detail = body.detail
  if (typeof detail === 'string') return { message: detail }
  return isProblem(detail) ? detail : undefined
}

function messageFor(status: number, problem?: ApiProblem): string {
  if (problem?.message) return problem.message
  if (status === 401) return 'Your session has expired. Please sign in again.'
  if (status === 403) return 'You do not have permission to complete this action.'
  if (status === 404) return 'The requested resource could not be found.'
  return 'The request could not be completed. Please try again.'
}

/**
 * Calls the same-origin Next.js API proxy. The proxy forwards requests to the
 * FastAPI service, which keeps browser CORS configuration out of UI code.
 */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { accessToken, body, headers, ...init } = options
  const requestHeaders = new Headers(headers)

  if (accessToken) requestHeaders.set('Authorization', `Bearer ${accessToken}`)

  const response = await fetch(path, {
    ...init,
    body,
    headers: requestHeaders,
  })

  if (!response.ok) {
    const problem = await readProblem(response)
    throw new ApiError(messageFor(response.status, problem), response.status, problem)
  }

  return response.json() as Promise<T>
}
