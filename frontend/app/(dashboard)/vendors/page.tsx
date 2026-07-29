'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

type Vendor = {
  id: number
  name: string
  category: string
  active: boolean
  incident_count: number
  aliases: string[]
}

const CATEGORIES = ['', 'cloud', 'identity', 'hr', 'cicd', 'healthcare', 'finance', 'other']

const emptyForm = { name: '', aliases: '', category: '' }

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState<{ msg: string; ok: boolean } | null>(null)

  // Add modal
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState(emptyForm)
  const [adding, setAdding] = useState(false)

  // Edit modal
  const [editVendor, setEditVendor] = useState<Vendor | null>(null)
  const [editForm, setEditForm] = useState(emptyForm)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    loadVendors()
  }, [])

  function loadVendors() {
    api.get('vendors')
      .then(data => setVendors(Array.isArray(data) ? data : data.items ?? []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  function flash(msg: string, ok = true) {
    setFeedback({ msg, ok })
    setTimeout(() => setFeedback(null), 4000)
  }

  // ── Add vendor ──
  async function handleAdd() {
    if (!addForm.name.trim()) return
    setAdding(true)
    try {
      const aliases = addForm.aliases
        .split(',').map(a => a.trim()).filter(Boolean)
      const created = await api.post('vendors', {
        name: addForm.name.trim(),
        aliases,
        category: addForm.category,
      })
      setVendors(v => [...v, created])
      setShowAdd(false)
      setAddForm(emptyForm)
      flash(`Vendor '${created.name}' added.`)
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : 'Failed to add vendor.', false)
    } finally {
      setAdding(false)
    }
  }

  // ── Open edit modal ──
  function openEdit(v: Vendor) {
    setEditVendor(v)
    setEditForm({
      name: v.name,
      aliases: (v.aliases ?? []).join(', '),
      category: v.category ?? '',
    })
  }

  // ── Save edit ──
  async function handleEdit() {
    if (!editVendor) return
    setEditing(true)
    try {
      const aliases = editForm.aliases
        .split(',').map(a => a.trim()).filter(Boolean)
      const updated = await api.patch(`vendors/${editVendor.id}`, {
        name: editForm.name.trim(),
        aliases,
        category: editForm.category,
      })
      setVendors(v => v.map(x => x.id === updated.id ? updated : x))
      setEditVendor(null)
      flash(`Vendor '${updated.name}' updated.`)
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : 'Failed to update vendor.', false)
    } finally {
      setEditing(false)
    }
  }

  // ── Toggle active ──
  async function handleToggle(vendor: Vendor) {
    try {
      const updated = await api.patch(`vendors/${vendor.id}`, { active: !vendor.active })
      setVendors(v => v.map(x => x.id === updated.id ? updated : x))
      flash(`'${updated.name}' ${updated.active ? 'activated' : 'deactivated'}.`)
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : 'Failed to toggle vendor.', false)
    }
  }

  // ── Delete vendor ──
  async function handleDelete(vendor: Vendor) {
    if (!confirm(`Delete '${vendor.name}'? This cannot be undone.`)) return
    try {
      await api.delete(`vendors/${vendor.id}`)
      setVendors(v => v.filter(x => x.id !== vendor.id))
      flash(`Vendor '${vendor.name}' deleted.`)
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : 'Failed to delete vendor.', false)
    }
  }

  if (loading) return <div className="text-gray-400 text-sm py-12 text-center">Loading vendors…</div>
  if (error)   return <div className="text-red-500 text-sm py-12 text-center">{error}</div>

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Vendors</h1>
          <p className="text-sm text-gray-500 mt-0.5">{vendors.length} monitored vendors</p>
        </div>
        <button
          onClick={() => { setShowAdd(true); setAddForm(emptyForm) }}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors shadow-sm"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Vendor
        </button>
      </div>

      {/* Feedback */}
      {feedback && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm border ${feedback.ok ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
          {feedback.msg}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Vendor', 'Category', 'Aliases', 'Incidents', 'Status', 'Actions'].map(h => (
                <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {vendors.map(v => (
              <tr key={v.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{v.name}</td>
                <td className="px-4 py-3 text-gray-500">{v.category || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {(v.aliases ?? []).slice(0, 3).map(a => (
                      <span key={a} className="bg-gray-100 text-gray-600 text-xs px-1.5 py-0.5 rounded">{a}</span>
                    ))}
                    {(v.aliases ?? []).length > 3 && (
                      <span className="text-xs text-gray-400">+{v.aliases.length - 3}</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-700 font-medium">{v.incident_count ?? 0}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${v.active ? 'text-emerald-700' : 'text-gray-400'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${v.active ? 'bg-emerald-500' : 'bg-gray-300'}`} />
                    {v.active ? 'Active' : 'Paused'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => openEdit(v)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleToggle(v)}
                      className="text-xs text-gray-500 hover:text-gray-700 font-medium transition-colors"
                    >
                      {v.active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => handleDelete(v)}
                      className="text-xs text-red-500 hover:text-red-700 font-medium transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {vendors.length === 0 && (
          <div className="text-center py-16 text-gray-400 text-sm">No vendors yet.</div>
        )}
      </div>

      {/* Add Modal */}
      {showAdd && (
        <Modal title="Add Vendor" onClose={() => setShowAdd(false)}>
          <VendorForm
            form={addForm}
            onChange={setAddForm}
            onSubmit={handleAdd}
            onCancel={() => setShowAdd(false)}
            submitting={adding}
            submitLabel="Add Vendor"
          />
        </Modal>
      )}

      {/* Edit Modal */}
      {editVendor && (
        <Modal title={`Edit — ${editVendor.name}`} onClose={() => setEditVendor(null)}>
          <VendorForm
            form={editForm}
            onChange={setEditForm}
            onSubmit={handleEdit}
            onCancel={() => setEditVendor(null)}
            submitting={editing}
            submitLabel="Save Changes"
          />
        </Modal>
      )}
    </div>
  )
}

// ── Shared modal shell ──
function Modal({ title, onClose, children }: {
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}

// ── Vendor form (shared by add + edit) ──
function VendorForm({ form, onChange, onSubmit, onCancel, submitting, submitLabel }: {
  form: { name: string; aliases: string; category: string }
  onChange: (f: { name: string; aliases: string; category: string }) => void
  onSubmit: () => void
  onCancel: () => void
  submitting: boolean
  submitLabel: string
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Vendor name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={form.name}
          onChange={e => onChange({ ...form, name: e.target.value })}
          onKeyDown={e => e.key === 'Enter' && onSubmit()}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="e.g. Okta"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Aliases <span className="text-gray-400 font-normal">(comma separated)</span>
        </label>
        <input
          type="text"
          value={form.aliases}
          onChange={e => onChange({ ...form, aliases: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="e.g. Okta Inc, OKTA"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
        <select
          value={form.category}
          onChange={e => onChange({ ...form, category: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
        >
          {CATEGORIES.map(c => (
            <option key={c} value={c}>{c || '— none —'}</option>
          ))}
        </select>
      </div>
      <div className="flex gap-3 pt-2">
        <button
          onClick={onSubmit}
          disabled={submitting || !form.name.trim()}
          className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors"
        >
          {submitting ? 'Saving…' : submitLabel}
        </button>
        <button
          onClick={onCancel}
          className="flex-1 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 text-sm font-medium py-2 rounded-lg transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}