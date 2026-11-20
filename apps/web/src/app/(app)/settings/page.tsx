'use client'

import { Settings, User, Building2, LogOut } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { clearSession, getSession } from '@/lib/session'

export default function SettingsPage() {
  const router = useRouter()
  const session = getSession()

  function handleLogout() {
    clearSession()
    router.push('/login')
  }

  const fieldStyle: React.CSSProperties = {
    fontSize: 13,
    fontWeight: 'var(--font-weight-medium)',
    color: 'var(--color-text-secondary)',
    marginBottom: 6,
  }

  const valueStyle: React.CSSProperties = {
    fontSize: 14,
    fontWeight: 'var(--font-weight-semibold)',
  }

  return (
    <>
      {/* Profile */}
      <div className="card">
        <div className="card-header">
          <User />
          Profile
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 480 }}>
          <div>
            <div style={fieldStyle}>Name</div>
            <div style={valueStyle}>{session?.user.name ?? '—'}</div>
          </div>
          <div>
            <div style={fieldStyle}>Email</div>
            <div style={valueStyle}>{session?.user.email ?? '—'}</div>
          </div>
          <div>
            <div style={fieldStyle}>Role</div>
            <div style={{ ...valueStyle, textTransform: 'capitalize' }}>{session?.user.role ?? '—'}</div>
          </div>
        </div>
      </div>

      {/* Organization */}
      <div className="card">
        <div className="card-header">
          <Building2 />
          Organization
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 480 }}>
          <div>
            <div style={fieldStyle}>Name</div>
            <div style={valueStyle}>{session?.organization.name ?? '—'}</div>
          </div>
          <div>
            <div style={fieldStyle}>Plan</div>
            <div style={{ ...valueStyle, textTransform: 'capitalize' }}>{session?.organization.plan ?? '—'}</div>
          </div>
        </div>
      </div>

      {/* Account */}
      <div className="card">
        <div className="card-header">
          <Settings />
          Account
        </div>
        <button
          onClick={handleLogout}
          className="btn btn-danger-outline"
        >
          <LogOut />
          Sign Out
        </button>
      </div>
    </>
  )
}
