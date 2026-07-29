'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { api } from '@/lib/api'

type Incident = {
  id: number
  title: string
  vendor: string
  severity: string
  alert_status: string
  incident_type: string
  source_feed: string
  soc_criteria: string[]
  summary: string
  ai_reason: string
  article_link: string
  detected_at: string
  notified_at: string | null
  acknowledged_at: string | null
  notes: string
  event_classification: string
}

const severityClass: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high:     'bg-orange-100 text-orange-700 border-orange-200',
  medium:   'bg-blue-100 text-blue-700 border-blue-200',
  low:      'bg-green-100 text-green-700 border-green-200',
  unknown:  'bg-gray-100 text-gray-600 border-gray-200',
}

const statusClass: Record<string, string> = {
  new:            'bg-yellow-100 text-yellow-700',
  notified:       'bg-blue-100 text-blue-700',
  acknowledged:   'bg-indigo-100 text-indigo-700',
  resolved:       'bg-emerald-100 text-emerald-700',
  false_positive: 'bg-gray-100 text-gray-500',
}

const classificationClass: Record<string, string> = {
  unclassified:     'bg-gray-100 text-gray-500',
  system_event:     'bg-amber-100 text-amber-700',
  system_incident:  'bg-red-100 text-red-700',
}

export default function IncidentDetailPage() {
  const { id } = useParams()
  const router = useRouter()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [notes, setNotes] = useState('')
  const [acting, setActing] = useState(false)
  const [feedback, setFeedback] = useState<{ msg: string; ok: boolean } | null>(null)

  useEffect(() => {
    api.get(`incidents/${id}`)
      .then(data => {
        setIncident(data)
        setNotes(data.notes ?? '')
      })
      .finally(() => setLoading(false))
  }, [id])

  // Maps display status back to the action verb the API expects
  const STATUS_TO_ACTION: Record<string, string> = {
    acknowledged:   'acknowledge',
    resolved:       'resolve',
    false_positive: 'false_positive',
    new:            'reopen',
  }

  async function performAction(newStatus: string) {
    if (!incident) return
    setActing(true)
    setFeedback(null)
    const action = STATUS_TO_ACTION[newStatus] ?? newStatus
    try {
      const updated = await api.patch(`incidents/${id}/action`, {
        action,
        notes: notes || undefined,
      })
      setIncident(updated)
      setFeedback({ msg: `Marked as ${newStatus.replace(/_/g, ' ')}.`, ok: true })
    } catch (e: unknown) {
      setFeedback({ msg: e instanceof Error ? e.message : 'Action failed.', ok: false })
    } finally {
      setActing(false)
    }
  }

  async function saveNotes() {
    if (!incident) return
    setActing(true)
    setFeedback(null)
    try {
      const updated = await api.patch(`incidents/${id}/notes`, { notes })
      setIncident(updated)
      setFeedback({ msg: 'Notes saved.', ok: true })
    } catch (e: unknown) {
      setFeedback({ msg: e instanceof Error ? e.message : 'Save failed.', ok: false })
    } finally {
      setActing(false)
    }
  }

  async function setClassification(classification: string) {
    if (!incident) return
    setActing(true)
    setFeedback(null)
    try {
      const updated = await api.patch(`incidents/${id}/action`, { action: classification })
      setIncident(updated)
      setFeedback({ msg: `Classified as ${classification.replace(/_/g, ' ')}.`, ok: true })
    } catch (e: unknown) {
      setFeedback({ msg: e instanceof Error ? e.message : 'Classification failed.', ok: false })
    } finally {
      setActing(false)
    }
  }

  if (loading) return <div className="text-gray-400 text-sm py-12 text-center">Loading…</div>
  if (!incident) return <div className="text-red-500 text-sm py-12 text-center">Incident not found.</div>

  const status = incident.alert_status
  const cls = incident.event_classification ?? 'unclassified'

  return (
    <div>
      {/* Back */}
      <div className="mb-5">
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Incidents
        </Link>
      </div>

      {/* Feedback banner */}
      {feedback && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm border ${feedback.ok ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
          {feedback.msg}
        </div>
      )}

      {/* Header card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border ${severityClass[incident.severity] ?? severityClass.unknown}`}>
            {incident.severity.toUpperCase()}
          </span>
          <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${statusClass[status] ?? 'bg-gray-100 text-gray-500'}`}>
            {status.replace(/_/g, ' ')}
          </span>
          {incident.incident_type && (
            <span className="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-md">{incident.incident_type}</span>
          )}
        </div>
        <h1 className="text-xl font-semibold text-gray-900 mb-1">{incident.title}</h1>
        <p className="text-sm text-gray-500">{incident.vendor} · {incident.source_feed} · {incident.detected_at?.slice(0, 10)}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* LEFT — details */}
        <div className="lg:col-span-2 space-y-4">

          {/* Summary */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Summary</h2>
            <p className="text-sm text-gray-700 leading-relaxed">{incident.summary || '—'}</p>
          </div>

          {/* AI Classification */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">AI Classification Reason</h2>
            <p className="text-sm text-gray-700 leading-relaxed">{incident.ai_reason || '—'}</p>
          </div>

          {/* TSC Criteria */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">TSC Criteria Mapped</h2>
            <div className="flex flex-wrap gap-1.5">
              {(incident.soc_criteria ?? []).map(c => (
                <span key={c} className="bg-indigo-50 text-indigo-700 text-xs px-2.5 py-1 rounded-md font-medium">{c}</span>
              ))}
              {!incident.soc_criteria?.length && <span className="text-sm text-gray-400">None mapped</span>}
            </div>
          </div>

          {/* Source */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Source Article</h2>
            {incident.article_link
              ? <a href={incident.article_link} target="_blank" rel="noopener noreferrer"
                  className="text-sm text-indigo-600 hover:underline break-all">{incident.article_link}</a>
              : <span className="text-sm text-gray-400">—</span>}
          </div>

          {/* Notes */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Analyst Notes</h2>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              placeholder="Add notes about this incident…"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
            <button
              onClick={saveNotes}
              disabled={acting}
              className="mt-2 bg-gray-800 hover:bg-gray-900 disabled:opacity-50 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              {acting ? 'Saving…' : 'Save notes'}
            </button>
          </div>
        </div>

        {/* RIGHT — triage actions */}
        <div className="space-y-4">

          {/* Triage actions */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">Triage Actions</h2>
            <div className="space-y-2">
              {status !== 'acknowledged' && status !== 'resolved' && status !== 'false_positive' && (
                <button
                  onClick={() => performAction('acknowledged')}
                  disabled={acting}
                  className="w-full flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Acknowledge
                </button>
              )}
              {status !== 'resolved' && status !== 'false_positive' && (
                <button
                  onClick={() => performAction('resolved')}
                  disabled={acting}
                  className="w-full flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Resolve
                </button>
              )}
              {status !== 'false_positive' && (
                <button
                  onClick={() => performAction('false_positive')}
                  disabled={acting}
                  className="w-full flex items-center gap-2 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-700 border border-gray-300 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                  </svg>
                  Mark False Positive
                </button>
              )}
              {(status === 'resolved' || status === 'false_positive') && (
                <button
                  onClick={() => performAction('new')}
                  disabled={acting}
                  className="w-full flex items-center gap-2 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-700 border border-gray-300 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Reopen
                </button>
              )}
            </div>
          </div>

          {/* Classification */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Event Classification</h2>
            <p className="text-xs text-gray-400 mb-3">Classify for SOC report scoping</p>
            <div className="space-y-1.5">
              {(['unclassified', 'system_event', 'system_incident'] as const).map(c => (
                <button
                  key={c}
                  onClick={() => setClassification(c)}
                  disabled={acting || cls === c}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                    cls === c
                      ? `${classificationClass[c]} border-transparent`
                      : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {cls === c && <span className="mr-1">✓</span>}
                  {c.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">Lifecycle Timeline</h2>
            <ol className="relative border-l border-gray-200 ml-2 space-y-4">
              {[
                { label: 'Detected', date: incident.detected_at, color: 'bg-indigo-500' },
                { label: 'Notified', date: incident.notified_at, color: 'bg-blue-400' },
                { label: 'Acknowledged', date: incident.acknowledged_at, color: 'bg-amber-400' },
              ].map(item => (
                <li key={item.label} className="ml-4">
                  <div className={`absolute w-2.5 h-2.5 ${item.date ? item.color : 'bg-gray-200'} rounded-full -left-1.5 mt-0.5`} />
                  <p className="text-xs font-semibold text-gray-700">{item.label}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {item.date ? item.date.slice(0, 16).replace('T', ' ') + ' UTC' : 'Pending'}
                  </p>
                </li>
              ))}
            </ol>
          </div>

        </div>
      </div>
    </div>
  )
}