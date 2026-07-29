'use client'

import { useState } from 'react'

export default function ChangePasswordPage() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit() {
    setError(null)
    if (!form.current_password) {
      setError('Please enter your current password.')
      return
    }
    if (form.new_password.length < 10) {
      setError('Password must be at least 10 characters.')
      return
    }
    if (form.new_password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${window.location.origin}/api/proxy/v1/profile/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = data.detail
        if (Array.isArray(detail)) {
          const msg = detail[0]?.msg || ''
          if (msg.includes('at least 10')) {
            setError('Password must be at least 10 characters.')
          } else if (msg.includes('Field required') || msg.includes('missing')) {
            setError('Please fill in all fields.')
          } else {
            setError(msg || 'Validation error.')
          }
        } else {
          setError(detail || 'Failed to update password.')
        }
        return
      }
      window.location.href = '/?message=Password+updated+successfully'
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-sm">
      <h1 className="text-lg font-semibold text-gray-900 mb-1">Change password</h1>
      <p className="text-sm text-gray-500 mb-6">Must be at least 10 characters.</p>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Current password</label>
          <input
            type="password"
            value={form.current_password}
            onChange={e => setForm(f => ({ ...f, current_password: e.target.value }))}
            placeholder="••••••••••"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
          <input
            type="password"
            value={form.new_password}
            onChange={e => setForm(f => ({ ...f, new_password: e.target.value }))}
            placeholder="••••••••••"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Confirm password</label>
          <input
            type="password"
            value={form.confirm_password}
            onChange={e => setForm(f => ({ ...f, confirm_password: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            placeholder="••••••••••"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={() => { window.location.href = '/' }}
            className="px-4 py-2 text-sm text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg transition-colors"
          >
            {loading ? 'Updating…' : 'Update password'}
          </button>
        </div>
      </div>
    </div>
  )
}
