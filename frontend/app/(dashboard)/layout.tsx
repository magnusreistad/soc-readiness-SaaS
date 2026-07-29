'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { useTheme } from '@/components/ThemeProvider'

// ─── Icons ────────────────────────────────────────────────────────────────────

function HomeIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>
    </svg>
  )
}
function AlertIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 3 9 16H3l9-16Z"/><path d="M12 10v5"/><circle cx="12" cy="17.5" r=".5" fill="currentColor"/>
    </svg>
  )
}
function BuildingIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 8h2M13 8h2M9 12h2M13 12h2M9 16h2M13 16h2"/>
    </svg>
  )
}
function ShieldIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>
    </svg>
  )
}
function SettingsIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>
    </svg>
  )
}
function ChevronRightIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="m9 6 6 6-6 6"/>
    </svg>
  )
}
function ChevronDownIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="m6 9 6 6 6-6"/>
    </svg>
  )
}
function DotsIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="19" cy="12" r="1.2" fill="currentColor"/>
    </svg>
  )
}
function BellIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 8a6 6 0 0 1 12 0c0 6 3 6 3 9H3c0-3 3-3 3-9Z"/><path d="M10 21a2 2 0 0 0 4 0"/>
    </svg>
  )
}
function SearchIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>
    </svg>
  )
}
function SunIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
    </svg>
  )
}
function MoonIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 13.5A9 9 0 1 1 10.5 3a7 7 0 0 0 10.5 10.5Z"/>
    </svg>
  )
}
function MonitorIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
    </svg>
  )
}
function LogoIcon() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6c0-1.1.9-2 2-2h9l5 5v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Z"/><path d="M8 11l3 3 5-6"/>
    </svg>
  )
}
function KeyIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
    </svg>
  )
}
function SignOutIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
    </svg>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getAvatarInitials(name: string): string {
  return name
    .split(/[\s.@_-]+/)
    .map(p => p[0]?.toUpperCase())
    .filter(Boolean)
    .slice(0, 2)
    .join('')
}

function getAvatarColors(name: string): { bg: string; color: string } {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360
  return { bg: `oklch(0.94 0.04 ${h})`, color: `oklch(0.45 0.12 ${h})` }
}

function getBreadcrumbs(pathname: string): string[] {
  if (pathname === '/') return ['Workspace', 'Overview']
  if (pathname.startsWith('/controls')) return ['Workspace', 'Controls']
  if (pathname.startsWith('/incidents')) return ['Workspace', 'Vendor incidents']
  if (pathname.startsWith('/vendors')) return ['Workspace', 'Vendors']
  if (pathname === '/settings/general') return ['Workspace', 'Settings', 'General']
  if (pathname === '/settings/users') return ['Workspace', 'Settings', 'Users']
  if (pathname.startsWith('/settings')) return ['Workspace', 'Settings']
  if (pathname.startsWith('/change-password')) return ['Workspace', 'Change password']
  return ['Workspace']
}

// ─── Command palette ──────────────────────────────────────────────────────────

const PALETTE_ITEMS = [
  { group: 'Navigate', label: 'Overview',              href: '/',                   icon: <HomeIcon /> },
  { group: 'Navigate', label: 'Vendor incidents',      href: '/incidents',          icon: <AlertIcon /> },
  { group: 'Navigate', label: 'Vendors',               href: '/vendors',            icon: <BuildingIcon /> },
  { group: 'Navigate', label: 'Controls',              href: '/controls',           icon: <ShieldIcon /> },
  { group: 'Navigate', label: 'Settings',              href: '/settings',           icon: <SettingsIcon /> },
  { group: 'Settings', label: 'Settings › General',   href: '/settings/general',   icon: <SettingsIcon /> },
  { group: 'Settings', label: 'Settings › Users',     href: '/settings/users',     icon: <SettingsIcon /> },
  { group: 'Account',  label: 'Change password',       href: '/change-password',    icon: <KeyIcon /> },
]

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const filtered = query.trim() === ''
    ? PALETTE_ITEMS
    : PALETTE_ITEMS.filter(i =>
        i.label.toLowerCase().includes(query.toLowerCase()) ||
        i.group.toLowerCase().includes(query.toLowerCase())
      )

  useEffect(() => { setActive(0) }, [query])
  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [open])

  function navigate(href: string) {
    router.push(href)
    onClose()
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(v => Math.min(v + 1, filtered.length - 1)) }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setActive(v => Math.max(v - 1, 0)) }
    if (e.key === 'Enter' && filtered[active]) navigate(filtered[active].href)
    if (e.key === 'Escape') onClose()
  }

  if (!open) return null

  const groups = Array.from(new Set(filtered.map(i => i.group)))

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
    >
      <div className="absolute inset-0 bg-black/40 dark:bg-black/60" onMouseDown={onClose} />
      <div className="relative w-full max-w-lg mx-4 bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 dark:border-gray-800">
          <SearchIcon />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search pages or actions…"
            className="flex-1 bg-transparent text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 outline-none"
          />
          <kbd className="text-[10px] font-mono text-gray-400 dark:text-gray-500 border border-gray-200 dark:border-gray-700 rounded px-1.5 py-0.5">esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto py-2">
          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-gray-400 dark:text-gray-500">No results</div>
          )}
          {groups.map(group => (
            <div key={group}>
              <div className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                {group}
              </div>
              {filtered.filter(i => i.group === group).map(item => {
                const idx = filtered.indexOf(item)
                return (
                  <button
                    key={item.href}
                    onMouseEnter={() => setActive(idx)}
                    onClick={() => navigate(item.href)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                      active === idx
                        ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400'
                        : 'text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    <span className="shrink-0 text-gray-400 dark:text-gray-500">{item.icon}</span>
                    {item.label}
                  </button>
                )
              })}
            </div>
          ))}
        </div>

        <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-800 flex items-center gap-4 text-[10px] text-gray-400 dark:text-gray-500">
          <span><kbd className="font-mono border border-gray-200 dark:border-gray-700 rounded px-1">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono border border-gray-200 dark:border-gray-700 rounded px-1">↵</kbd> open</span>
          <span><kbd className="font-mono border border-gray-200 dark:border-gray-700 rounded px-1">esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}

// ─── TopBar ───────────────────────────────────────────────────────────────────

function TopBar({ pathname, onOpenPalette }: { pathname: string; onOpenPalette: () => void }) {
  const crumbs = getBreadcrumbs(pathname)
  const { mode, setMode } = useTheme()

  function cycleTheme() {
    setMode(mode === 'light' ? 'dark' : mode === 'dark' ? 'system' : 'light')
  }

  return (
    <div className="h-12 px-6 flex items-center justify-between border-b border-gray-100 dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur sticky top-0 z-20">
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        {crumbs.map((crumb, i) => (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && (
              <span className="text-gray-300 dark:text-gray-600">
                <ChevronRightIcon size={12} />
              </span>
            )}
            <span className={i === crumbs.length - 1 ? 'text-gray-900 dark:text-gray-100 font-medium' : ''}>
              {crumb}
            </span>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-1.5">
        <button className="relative p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400">
          <BellIcon />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-red-500" />
        </button>
        <button
          onClick={onOpenPalette}
          className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400"
        >
          <SearchIcon />
        </button>
        <button
          onClick={cycleTheme}
          className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400"
          title={`Theme: ${mode} (click to cycle)`}
        >
          {mode === 'dark' ? <MoonIcon /> : mode === 'light' ? <SunIcon /> : <MonitorIcon />}
        </button>
        <span className="mx-0.5 h-5 w-px bg-gray-200 dark:bg-gray-800" />
        <button
          onClick={onOpenPalette}
          className="text-xs text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 font-mono transition-colors"
        >
          ⌘K
        </button>
      </div>
    </div>
  )
}

// ─── User menu ────────────────────────────────────────────────────────────────

function UserMenu({ onSignOut }: { onSignOut: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-colors"
      >
        <DotsIcon />
      </button>
      {open && (
        <div className="absolute bottom-full right-0 mb-2 w-44 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden z-50">
          <Link
            href="/change-password"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800 transition-colors"
          >
            <KeyIcon />
            Change password
          </Link>
          <button
            onClick={() => { setOpen(false); onSignOut() }}
            className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10 transition-colors"
          >
            <SignOutIcon />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Nav config ───────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { href: '/',          label: 'Overview',         icon: <HomeIcon /> },
  { href: '/incidents', label: 'Vendor incidents', icon: <AlertIcon /> },
  { href: '/vendors',   label: 'Vendors',           icon: <BuildingIcon /> },
  { href: '/controls',  label: 'Controls',          icon: <ShieldIcon /> },
  { href: '/settings',  label: 'Settings',          icon: <SettingsIcon /> },
]

// ─── Layout ───────────────────────────────────────────────────────────────────

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [userEmail, setUserEmail]       = useState('')
  const [displayName, setDisplayName]   = useState('')
  const [userRole, setUserRole]         = useState('analyst')
  const [newIncidents, setNewIncidents] = useState(0)
  const [paletteOpen, setPaletteOpen]   = useState(false)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session
      if (!session) return
      setUserEmail(session.user.email ?? '')
      const full: string = session.user.user_metadata?.full_name ?? session.user.user_metadata?.name ?? ''
      setDisplayName(full || (session.user.email ?? ''))
      try {
        const payload = JSON.parse(atob(session.access_token.split('.')[1]))
        setUserRole((payload.role as string) || 'analyst')
      } catch {
        setUserRole('analyst')
      }
    })
  }, [])

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(v => !v)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    fetch('/api/incidents?status=new&limit=1')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.total != null) setNewIncidents(Number(d.total)) })
      .catch(() => {})
  }, [])

  async function handleSignOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    window.location.href = '/login'
  }

  function isActive(href: string): boolean {
    if (href === '/') return pathname === '/'
    if (href === '/controls') return pathname === '/controls' || pathname.startsWith('/controls/')
    if (href === '/settings') return pathname === '/settings' || pathname.startsWith('/settings/')
    if (href === '/incidents') return pathname === '/incidents' || pathname.startsWith('/incidents/')
    return pathname.startsWith(href)
  }

  const name = displayName || userEmail
  const initials = getAvatarInitials(name)
  const { bg: avatarBg, color: avatarColor } = getAvatarColors(name)

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950">
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

      {/* ── Sidebar ── */}
      <aside className="w-56 shrink-0 h-[100dvh] sticky top-0 flex flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">

        {/* Workspace header */}
        <div className="px-3 py-4 border-b border-gray-100 dark:border-gray-800">
          <button className="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
            <span className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0">
              <LogoIcon />
            </span>
            <span className="flex-1 text-left min-w-0">
              <span className="block text-xs font-semibold text-gray-900 dark:text-gray-100 truncate">Vendor Threat</span>
              <span className="block text-xs text-gray-500 dark:text-gray-500 truncate">Monitor · SOC 2 Type 2</span>
            </span>
            <span className="text-gray-400 shrink-0">
              <ChevronDownIcon size={14} />
            </span>
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          {NAV_ITEMS.map(item => {
            const active = isActive(item.href)
            const badge = item.href === '/incidents' && newIncidents > 0 ? newIncidents : undefined
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-gray-50'
                }`}
              >
                <span className="shrink-0">{item.icon}</span>
                <span className="flex-1">{item.label}</span>
                {badge != null && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-red-500 text-white">
                    {badge}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        {/* User footer */}
        <div className="px-3 py-3 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2.5">
            <span
              className="inline-flex items-center justify-center rounded-full font-semibold text-[11px] shrink-0 select-none"
              style={{ width: 28, height: 28, background: avatarBg, color: avatarColor }}
            >
              {initials || '?'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-gray-900 dark:text-gray-100 truncate">
                {name || '—'}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-500 truncate capitalize">{userRole}</div>
            </div>
            <UserMenu onSignOut={handleSignOut} />
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar pathname={pathname} onOpenPalette={() => setPaletteOpen(true)} />
        <main className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950">
          <div className="min-h-full max-w-7xl mx-auto px-6 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
