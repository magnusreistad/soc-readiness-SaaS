'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
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
  detected_at: string
}

const severityClass: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high:     'bg-orange-100 text-orange-700 border-orange-200',
  medium:   'bg-blue-100 text-blue-700 border-blue-200',
  low:      'bg-green-100 text-green-700 border-green-200',
  unknown:  'bg-gray-100 text-gray-600 border-gray-200',
}

const statusClass: Record<string, string> = {
  new:           'bg-yellow-100 text-yellow-700',
  notified:      'bg-blue-100 text-blue-700',
  acknowledged:  'bg-indigo-100 text-indigo-700',
  resolved:      'bg-emerald-100 text-emerald-700',
  false_positive:'bg-gray-100 text-gray-500',
}

export default function IncidentsPage() {
  const router = useRouter()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('incidents')
      .then(inc => setIncidents(inc.items ?? inc))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-400 text-sm py-12 text-center">Loading incidents…</div>
  if (error)   return <div className="text-red-500 text-sm py-12 text-center">{error}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-50">Incidents</h1>
          <p className="text-sm text-gray-500 mt-0.5">{incidents.length} vendor threat incidents</p>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900/60 border-b border-gray-200 dark:border-gray-800">
            <tr>
              {['Severity', 'Vendor', 'Title', 'Source', 'TSC Criteria', 'Status', 'Detected'].map(h => (
                <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {incidents.map(inc => (
              <tr
                key={inc.id}
                onClick={() => router.push(`/incidents/${inc.id}`)}
                className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer"
              >
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border ${severityClass[inc.severity] ?? severityClass.unknown}`}>
                    {inc.severity.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{inc.vendor}</td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300 max-w-xs">
                  <span className="line-clamp-1">{inc.title}</span>
                  {inc.incident_type && <span className="block text-xs text-gray-400">{inc.incident_type}</span>}
                </td>
                <td className="px-4 py-3 text-gray-500">{inc.source_feed || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {(inc.soc_criteria ?? []).slice(0, 3).map(c => (
                      <span key={c} className="bg-indigo-50 text-indigo-700 text-xs px-1.5 py-0.5 rounded font-medium dark:bg-indigo-500/10 dark:text-indigo-400">
                        {c}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${statusClass[inc.alert_status] ?? 'bg-gray-100 text-gray-500'}`}>
                    {inc.alert_status.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                  {inc.detected_at?.slice(0, 10) ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {incidents.length === 0 && (
          <div className="text-center py-16 text-gray-400 text-sm">No incidents found.</div>
        )}
      </div>
    </div>
  )
}
