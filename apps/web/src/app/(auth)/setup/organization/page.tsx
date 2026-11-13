'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { AlertCircle, ArrowRight, Building2 } from 'lucide-react'
import { ApiError } from '@/lib/api-client'
import { setSession } from '@/lib/session'
import { login, readMe, register } from '@/services/auth.service'

export default function OrganizationSetupPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [organizationName, setOrganizationName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await register(name.trim(), email.trim(), password, organizationName.trim())
      const session = await login(email.trim(), password)
      const currentUser = await readMe(session.access_token)
      setSession({ ...currentUser, access_token: session.access_token })
      router.push('/setup/connector')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'We could not create your workspace. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-card">
      <div className="setup-step"><Building2 /> Step 1 of 2</div>
      <h1>Create your workspace</h1>
      <p className="auth-lede">Create an account and the first workspace for your team.</p>
      {error && <div className="error-alert" role="alert"><AlertCircle />{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-group"><label className="form-label" htmlFor="name">Your name</label><input className="form-input" id="name" value={name} onChange={(event) => setName(event.target.value)} required /></div>
        <div className="form-group"><label className="form-label" htmlFor="workspace">Workspace name</label><input className="form-input" id="workspace" value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required /></div>
        <div className="form-group"><label className="form-label" htmlFor="email">Email</label><input className="form-input" id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>
        <div className="form-group"><label className="form-label" htmlFor="password">Password</label><input className="form-input" id="password" type="password" autoComplete="new-password" minLength={1} value={password} onChange={(event) => setPassword(event.target.value)} required /></div>
        <button className="btn btn-primary auth-submit" disabled={loading} type="submit"><ArrowRight />{loading ? 'Creating workspace…' : 'Create workspace'}</button>
      </form>
      <p className="auth-footer">Already have an account? <Link href="/login">Sign in</Link></p>
    </div>
  )
}
