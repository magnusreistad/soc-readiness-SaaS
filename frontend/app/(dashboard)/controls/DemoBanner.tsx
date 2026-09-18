'use client'

import { useState } from 'react'

// Only set on the public demo deployment (see .env.demo.example) — absent
// entirely on the real production frontend, so this stays a no-op there.
// Mirrors the same check used to show the "View Demo" button on /login.
const DEMO_EMAIL    = process.env.NEXT_PUBLIC_DEMO_EMAIL
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD
export const DEMO_ENABLED = Boolean(DEMO_EMAIL && DEMO_PASSWORD)

type DemoBannerProps = {
  onOpenControl: () => void
}

export function DemoBanner({ onOpenControl }: DemoBannerProps) {
  const [dismissed, setDismissed] = useState(false)

  if (!DEMO_ENABLED || dismissed) return null

  return (
    <div className="flex items-start gap-3 bg-blue-50 dark:bg-blue-500/10 border border-blue-100 dark:border-blue-500/20 rounded-lg px-4 py-3">
      <svg className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p className="flex-1 text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
        Try the automated evidence collector — open{' '}
        <button
          type="button"
          onClick={onOpenControl}
          className="font-semibold underline hover:no-underline"
        >
          CC8-001 (Change Management Approval Testing)
        </button>{' '}
        and pull live evidence directly from GitHub.
      </p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="text-blue-400 hover:text-blue-600 dark:hover:text-blue-300 shrink-0"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
