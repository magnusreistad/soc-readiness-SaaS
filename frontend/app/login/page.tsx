'use client'

import dynamic from 'next/dynamic'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import Link from "next/link"

// Only set on the public demo deployment (see .env.demo.example) — absent
// entirely on the real production frontend, so this stays a no-op there.
const DEMO_EMAIL    = process.env.NEXT_PUBLIC_DEMO_EMAIL
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD
const DEMO_ENABLED  = Boolean(DEMO_EMAIL && DEMO_PASSWORD)

function LoginPageContent() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const msg = params.get('message')
    if (msg) setSuccessMessage(msg)
  }, [])

  async function signIn(loginEmail: string, loginPassword: string) {
    const supabase = createClient()
    const { error } = await supabase.auth.signInWithPassword({
      email: loginEmail,
      password: loginPassword,
    })
    if (error) {
      setError(error.message)
      return false
    }
    router.push('/')
    router.refresh()
    return true
  }

  async function handleLogin() {
    setLoading(true)
    setError('')
    const ok = await signIn(email, password)
    if (!ok) setLoading(false)
  }

  async function handleDemoLogin() {
    if (!DEMO_EMAIL || !DEMO_PASSWORD) return
    setDemoLoading(true)
    setError('')
    const ok = await signIn(DEMO_EMAIL, DEMO_PASSWORD)
    if (!ok) setDemoLoading(false)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="flex flex-col items-center mb-8">
            <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">SOC Readiness SaaS</h1>
            <p className="text-sm text-gray-500 mt-1">SOC 2 Compliance Platform</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}
          {successMessage && (
            <div className="mb-4 rounded-lg bg-green-50 border border-green-200 text-green-700 px-4 py-3 text-sm">
              {successMessage}
            </div>
          )}

          {DEMO_ENABLED && (
            <div className="mb-6 rounded-lg bg-indigo-50 border border-indigo-100 px-4 py-3 text-center">
              <p className="text-sm text-indigo-900 mb-2">
                Want to explore first? Try the live demo — no signup required.
              </p>
              <button
                type="button"
                onClick={handleDemoLogin}
                disabled={demoLoading}
                className="w-full bg-white border border-indigo-300 hover:bg-indigo-100 disabled:opacity-50 text-indigo-700 font-medium py-2 rounded-lg text-sm transition-colors"
              >
                {demoLoading ? 'Loading demo…' : 'View Demo'}
              </button>
            </div>
          )}

          <div className="relative z-50 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="••••••••"
              />
            </div>
            <button
              onClick={handleLogin}
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={() => router.push('/reset-password')}
              className="text-sm text-indigo-600 hover:underline w-full text-center"
            >
              Forgot password?
            </button>
            <p className="text-center text-sm text-gray-500">
              Don&apos;t have a workspace?{" "}
              <Link href="/signup" className="text-indigo-600 hover:underline font-medium">
                Create one
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Disable SSR entirely for login page — avoids hydration mismatch from
// window.location.search and browser extension interference
const LoginPage = dynamic(() => Promise.resolve(LoginPageContent), { ssr: false })

export default LoginPage