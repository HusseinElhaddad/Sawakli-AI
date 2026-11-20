'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { AlertCircle, Brain, LogIn } from 'lucide-react'
import { ApiError } from '@/lib/api-client'
import { setSession } from '@/lib/session'
import { login, readMe } from '@/services/auth.service'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const authenticated = await login(email.trim(), password)
      const currentUser = await readMe(authenticated.access_token)
      setSession({ ...currentUser, access_token: authenticated.access_token })
      router.push('/setup/connector')
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 401
          ? 'Invalid email or password. Check your credentials and try again.'
          : caught instanceof ApiError ? caught.message : 'We could not sign you in. Please try again.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-card">
      <div className="brand-lockup"><span className="brand-mark"><Brain /></span><span>Sawakli AI</span></div>
      <h1>Sign in to your workspace</h1>
      <p className="auth-lede">Use your Sawakli account to manage your organization&apos;s data sources.</p>
      {error && <div className="error-alert" role="alert"><AlertCircle />{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-group"><label className="form-label" htmlFor="email">Email</label><input className="form-input" id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>
        <div className="form-group"><label className="form-label" htmlFor="password">Password</label><input className="form-input" id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></div>
        <button className="btn btn-primary auth-submit" disabled={loading} type="submit"><LogIn />{loading ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="auth-footer">New to Sawakli? <Link href="/setup/organization">Create a workspace</Link></p>
    </div>
  )
}
