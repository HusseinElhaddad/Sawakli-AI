import { apiRequest } from '@/lib/api-client'
import type { AuthResponse, MeResponse, Organization, User } from '@/types'

export async function login(email: string, password: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    headers: { 'Content-Type': 'application/json' },
  })
}

type RegisterResponse = {
  user: User
  organization: Organization
}

export async function register(
  name: string,
  email: string,
  password: string,
  organizationName: string,
): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      name,
      email,
      password,
      organization_name: organizationName,
    }),
    headers: { 'Content-Type': 'application/json' },
  })
}

export function readMe(accessToken: string): Promise<MeResponse> {
  return apiRequest<MeResponse>('/api/auth/me', {
    method: 'GET',
    accessToken,
  })
}
