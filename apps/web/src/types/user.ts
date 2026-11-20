export type User = {
  id: string
  name: string
  email: string
  role?: string
}

export type AuthResponse = {
  user: User
  access_token: string
  token_type: string
}

export type MeResponse = {
  user: User
  organization: Organization
}
import type { Organization } from './organization'
