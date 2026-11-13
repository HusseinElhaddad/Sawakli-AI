'use client'

import { useSyncExternalStore } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Megaphone,
  Lightbulb,
  FileBarChart,
  Settings,
  Brain,
  User,
} from 'lucide-react'
import { getSession } from '@/lib/session'
import { useRecommendations } from '@/hooks/useRecommendations'
import styles from './sidebar.module.css'

const subscribe = () => () => {}
const getTrue = () => true
const getFalse = () => false

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', route: '/dashboard' },
  { icon: Megaphone, label: 'Campaigns', route: '/campaigns' },
  { icon: Lightbulb, label: 'Recommendations', route: '/recommendations' },
  { icon: FileBarChart, label: 'Reports', route: '/reports' },
  { icon: Settings, label: 'Settings', route: '/settings' },
] as const

export function Sidebar() {
  const pathname = usePathname()
  const mounted = useSyncExternalStore(subscribe, getTrue, getFalse)
  const session = mounted ? getSession() : null

  const orgId = session?.organization.id ?? ''
  const { data: recommendations } = useRecommendations(orgId)
  const pendingCount = recommendations?.filter((r) => r.status === 'pending').length ?? 0

  return (
    <aside className={styles.sidebar}>
      <Link href="/dashboard" className={styles.brand}>
        <div className={styles.brandIcon}>
          <Brain />
        </div>
        <span className={styles.brandName}>Sawakli</span>
      </Link>

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.route ||
            (item.route !== '/dashboard' && pathname.startsWith(item.route + '/'))

          return (
            <Link
              key={item.route}
              href={item.route}
              className={`${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              {isActive && <span className={styles.activeBar} />}
              <item.icon className={styles.navIcon} />
              <span>{item.label}</span>
              {item.label === 'Recommendations' && mounted && pendingCount > 0 && (
                <span className={styles.badge}>{pendingCount}</span>
              )}
            </Link>
          )
        })}
      </nav>

      <div className={styles.footer}>
        <div className={styles.avatar}>
          <User />
        </div>
        {mounted && (
          <div className={styles.userInfo}>
            <div className={styles.userName}>
              {session?.user.name ?? 'Guest'}
            </div>
            <div className={styles.orgName}>
              {session?.organization.name ?? ''}
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
