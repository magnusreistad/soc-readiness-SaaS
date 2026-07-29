'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

type Control = {
  id: number
  control_id: string
  title: string
  owner: string
  tsc_criteria: string[]
  audit_bucket: string
  next_action: string | null
  last_evidence_at: string | null
  worst_verdict: string | null
  evidence_count: number
  frequency: string | null
}

type Incident = {
  id: number
  title: string
  vendor: string
  severity: string
  alert_status: string
  soc_criteria: string[]
  detected_at: string
  source_feed: string
}

type IncidentStats = {
  total: number
  new: number
  notified: number
  acknowledged: number
  resolved: number
  critical: number
  high: number
  medium: number
  low: number
  unknown: number
}

const TSC_LABELS: Record<string, string> = {
  CC1: 'CC1 — Control Environment',
  CC2: 'CC2 — Communication & Information',
  CC3: 'CC3 — Risk Assessment',
  CC4: 'CC4 — Monitoring Activities',
  CC5: 'CC5 — Control Activities',
  CC6: 'CC6 — Logical & Physical Access',
  CC7: 'CC7 — System Operations',
  CC8: 'CC8 — Change Management',
  CC9: 'CC9 — Risk Mitigation',
  A1: 'A1 — Availability',
  C1: 'C1 — Confidentiality',
  PI1: 'PI1 — Processing Integrity',
  P1: 'P1 — Privacy',
}

const TSC_ORDER = ['CC1','CC2','CC3','CC4','CC5','CC6','CC7','CC8','CC9','A1','C1','PI1','P1']


const bucketDot: Record<string, string> = {
  audit_ready: 'bg-emerald-500',
  at_risk:     'bg-amber-400',
  blocked:     'bg-amber-400',
  no_evidence: 'bg-gray-300',
}

const bucketBadge: Record<string, string> = {
  audit_ready: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20',
  at_risk:     'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20',
  blocked:     'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20',
  no_evidence: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700',
}

const bucketLabel: Record<string, string> = {
  audit_ready: 'Audit ready',
  at_risk:     'Improvements Recommended',
  blocked:     'Improvements Recommended',
  no_evidence: 'No evidence',
}

const sevBadge: Record<string, string> = {
  critical: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20',
  high: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/10 dark:text-orange-400 dark:border-orange-500/20',
  medium: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20',
  low: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20',
  unknown: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700',
}

const statusBadge: Record<string, string> = {
  new: 'bg-red-50 text-red-700 border-red-200',
  notified: 'bg-amber-50 text-amber-700 border-amber-200',
  acknowledged: 'bg-blue-50 text-blue-700 border-blue-200',
  resolved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  false_positive: 'bg-gray-100 text-gray-600 border-gray-200',
}

const statusLabel: Record<string, string> = {
  new: 'New',
  notified: 'Notified',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
  false_positive: 'False positive',
}

function ChevronRight() {
  return (
    <svg className="w-3.5 h-3.5 text-gray-300 dark:text-gray-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 6l6 6-6 6" />
    </svg>
  )
}

function ArrowRight() {
  return (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14m-7-7 7 7-7 7" />
    </svg>
  )
}

function ControlIdBadge({ id }: { id: string }) {
  return (
    <span className="inline-flex items-center justify-center rounded-md border border-indigo-200 bg-indigo-50 text-indigo-700 text-xs font-mono font-bold px-2 py-0.5 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-500/20 whitespace-nowrap shrink-0">
      {id}
    </span>
  )
}

export default function OverviewPage() {
  const router = useRouter()
  const [controls, setControls] = useState<Control[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [stats, setStats] = useState<IncidentStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get('controls'),
      api.get('incidents'),
      api.get('incidents/stats'),
    ])
      .then(([ctrlData, incData, statsData]) => {
        setControls(ctrlData.items ?? ctrlData)
        setIncidents(incData.items ?? incData)
        setStats(statsData)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-400 text-sm">
        Loading overview…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-red-500 text-sm">
        {error}
      </div>
    )
  }

  const total = controls.length
  const ready = controls.filter(c => c.audit_bucket === 'audit_ready').length
  const atRisk = controls.filter(c => c.audit_bucket === 'at_risk' || c.audit_bucket === 'blocked').length
  const blocked = controls.filter(c => c.audit_bucket === 'no_evidence').length
  const readinessPct = total > 0 ? Math.round((ready / total) * 100) : 0

  const openIncidents = incidents.filter(
    i => i.alert_status !== 'resolved' && i.alert_status !== 'false_positive'
  )

  const tscCategories = TSC_ORDER.map(prefix => {
    const items = controls.filter(c =>
      c.tsc_criteria?.some(code => code === prefix || code.startsWith(prefix + '.'))
    )
    if (items.length === 0) return null
    const catReady = items.filter(c => c.audit_bucket === 'audit_ready').length
    return {
      prefix,
      label: TSC_LABELS[prefix] ?? prefix,
      total: items.length,
      ready: catReady,
      pct: Math.round((catReady / items.length) * 100),
    }
  }).filter(Boolean) as Array<{ prefix: string; label: string; total: number; ready: number; pct: number }>

  const needsAttention = controls
    .filter(c => c.audit_bucket !== 'audit_ready')
    .slice(0, 5)

  const recentEvals = controls
    .filter(c => c.last_evidence_at && c.evidence_count > 0)
    .sort((a, b) => {
      if (!a.last_evidence_at) return 1
      if (!b.last_evidence_at) return -1
      return new Date(b.last_evidence_at).getTime() - new Date(a.last_evidence_at).getTime()
    })
    .slice(0, 4)

  const totalNeedsAttention = controls.filter(c => c.audit_bucket !== 'audit_ready').length
  const newIncidentsCount = openIncidents.filter(i => i.alert_status === 'new').length

  return (
    <div className="max-w-7xl mx-auto">

      {/* Page header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-1">
            Dashboard
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">
            SOC 2 readiness at a glance
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-2xl">
            An overview of your evidence readiness, vendor threat posture, and items requiring attention.
          </p>
        </div>
      </div>

      {/* Row 1: Readiness + Threat posture + At a glance */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mb-4">

        {/* Overall readiness */}
        <div className="md:col-span-5 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-3">
              Overall readiness
            </p>
            <div className="flex items-baseline gap-3">
              <span className="text-5xl font-semibold tracking-tight tabular-nums text-gray-900 dark:text-gray-50">
                {readinessPct}%
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {ready} / {total} controls audit-ready
              </span>
            </div>
            <div className="mt-4">
              <div className="h-2 w-full rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800 flex">
                {total > 0 && (
                  <>
                    <div className="h-full bg-emerald-500 transition-all" style={{ width: `${(ready / total) * 100}%` }} />
                    <div className="h-full bg-amber-500 transition-all" style={{ width: `${(atRisk / total) * 100}%` }} />
                    <div className="h-full bg-gray-300 dark:bg-gray-600 transition-all" style={{ width: `${(blocked / total) * 100}%` }} />
                  </>
                )}
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                  {ready} audit-ready
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                  {atRisk} improvements recommended
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600 shrink-0" />
                  {blocked} no evidence
                </span>
              </div>
            </div>
          </div>
          <div className="border-t border-gray-100 dark:border-gray-800 px-6 py-3 flex items-center justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">{total} controls in scope</span>
            <button
              onClick={() => router.push('/controls')}
              className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium inline-flex items-center gap-1"
            >
              Open controls <ArrowRight />
            </button>
          </div>
        </div>

        {/* Vendor threat posture */}
        <div className="md:col-span-4 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-3">
              Vendor threat posture
            </p>
            <div className="flex items-baseline gap-3">
              <span className="text-5xl font-semibold tracking-tight tabular-nums text-gray-900 dark:text-gray-50">
                {openIncidents.length}
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">open incidents</span>
            </div>
            <div className="mt-4 grid grid-cols-4 gap-2 text-center">
              {(['critical', 'high', 'medium', 'low'] as const).map(sev => {
                const count = openIncidents.filter(i => i.severity === sev).length
                const textColor =
                  sev === 'critical' ? 'text-red-600 dark:text-red-400' :
                  sev === 'high'     ? 'text-orange-600 dark:text-orange-400' :
                  sev === 'medium'   ? 'text-amber-600 dark:text-amber-400' :
                                       'text-blue-600 dark:text-blue-400'
                return (
                  <div key={sev} className="rounded-md border border-gray-100 dark:border-gray-800 py-2">
                    <div className={`text-xl font-semibold tabular-nums ${textColor}`}>{count}</div>
                    <div className="text-xs text-gray-500 capitalize">{sev}</div>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="border-t border-gray-100 dark:border-gray-800 px-6 py-3 flex items-center justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">{incidents.length} total incidents</span>
            <button
              onClick={() => router.push('/incidents')}
              className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium inline-flex items-center gap-1"
            >
              All incidents <ArrowRight />
            </button>
          </div>
        </div>

        {/* At a glance */}
        <div className="md:col-span-3 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-3">
              At a glance
            </p>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">New incidents</span>
                <span className="text-sm font-semibold tabular-nums text-red-600 dark:text-red-400">
                  {stats?.new ?? 0}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Controls with gaps</span>
                <span className="text-sm font-semibold tabular-nums text-amber-600 dark:text-amber-400">
                  {atRisk + blocked}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">No evidence yet</span>
                <span className="text-sm font-semibold tabular-nums text-gray-700 dark:text-gray-300">
                  {blocked}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Critical severity</span>
                <span className="text-sm font-semibold tabular-nums text-red-600 dark:text-red-400">
                  {stats?.critical ?? 0}
                </span>
              </div>
            </div>
          </div>
          <div className="border-t border-gray-100 dark:border-gray-800 px-6 py-3 text-xs text-gray-400 dark:text-gray-500">
            Live data
          </div>
        </div>
      </div>

      {/* Row 2: Recent evaluations + TSC breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4">

        {/* Recent evaluations */}
        <div className="lg:col-span-7 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="px-6 pt-5 pb-3 flex items-center justify-between border-b border-gray-100 dark:border-gray-800">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                Recently evaluated controls
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Controls with the most recent evidence uploads
              </p>
            </div>
            <button
              onClick={() => router.push('/controls')}
              className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium"
            >
              View all
            </button>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {recentEvals.length === 0 ? (
              <div className="px-6 py-8 text-sm text-gray-400 dark:text-gray-500 text-center">
                No evidence uploaded yet. Open a control to get started.
              </div>
            ) : (
              recentEvals.map(c => (
                <button
                  key={c.id}
                  onClick={() => router.push(`/controls?openControl=${c.id}`)}
                  className="w-full flex items-center gap-4 px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 text-left"
                >
                  <ControlIdBadge id={c.control_id} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {c.title}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 flex items-center gap-2">
                      <span>{c.evidence_count} file{c.evidence_count !== 1 ? 's' : ''}</span>
                      {c.last_evidence_at && (
                        <>
                          <span className="text-gray-300 dark:text-gray-700">·</span>
                          <span>{c.last_evidence_at.slice(0, 10)}</span>
                        </>
                      )}
                      {c.owner && (
                        <>
                          <span className="text-gray-300 dark:text-gray-700">·</span>
                          <span>{c.owner}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`inline-flex items-center rounded-full border text-xs font-medium px-2 py-0.5 ${bucketBadge[c.audit_bucket] ?? bucketBadge.no_evidence}`}>
                      {bucketLabel[c.audit_bucket] ?? 'No evidence'}
                    </span>
                    <ChevronRight />
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Readiness by TSC category */}
        <div className="lg:col-span-5 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="px-6 pt-5 pb-3 border-b border-gray-100 dark:border-gray-800">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Readiness by TSC category
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Audit-ready controls per Trust Services Criteria
            </p>
          </div>
          <div className="px-6 py-4 space-y-3">
            {tscCategories.length === 0 ? (
              <div className="text-sm text-gray-400 text-center py-4">No controls in scope.</div>
            ) : (
              tscCategories.map(cat => (
                <div key={cat.prefix}>
                  <div className="flex items-baseline justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{cat.label}</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 font-mono tabular-nums">
                      {cat.ready}/{cat.total}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          cat.pct >= 80 ? 'bg-emerald-500' :
                          cat.pct >= 50 ? 'bg-indigo-500' :
                                         'bg-amber-500'
                        }`}
                        style={{ width: `${cat.pct}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-gray-500 dark:text-gray-400 w-8 text-right tabular-nums">
                      {cat.pct}%
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Row 3: Active incidents + Needs attention */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">

        {/* Active incidents table */}
        <div className="lg:col-span-8 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="px-6 pt-5 pb-3 flex items-center justify-between border-b border-gray-100 dark:border-gray-800">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  Active vendor incidents
                </h2>
                {newIncidentsCount > 0 && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-red-500 text-white">
                    {newIncidentsCount} new
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                CVEs and advisories mapped to controls in scope
              </p>
            </div>
            <button
              onClick={() => router.push('/incidents')}
              className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium"
            >
              View all
            </button>
          </div>
          {openIncidents.length === 0 ? (
            <div className="px-6 py-8 text-sm text-gray-400 dark:text-gray-500 text-center">
              No open incidents.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/60">
                  <th className="px-6 py-2 text-left font-medium">Incident</th>
                  <th className="px-2 py-2 text-left font-medium">Severity</th>
                  <th className="px-2 py-2 text-left font-medium hidden sm:table-cell">Criteria</th>
                  <th className="px-2 py-2 text-left font-medium">Status</th>
                  <th className="px-6 py-2 text-right font-medium hidden md:table-cell">Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {openIncidents.slice(0, 5).map(inc => (
                  <tr
                    key={inc.id}
                    onClick={() => router.push(`/incidents/${inc.id}`)}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer"
                  >
                    <td className="px-6 py-3">
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-xs">
                        {inc.title}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {inc.vendor}{inc.source_feed ? ` · ${inc.source_feed}` : ''}
                      </div>
                    </td>
                    <td className="px-2 py-3">
                      <span className={`inline-flex items-center rounded-full border text-xs font-medium px-2 py-0.5 ${sevBadge[inc.severity] ?? sevBadge.unknown}`}>
                        {inc.severity.charAt(0).toUpperCase() + inc.severity.slice(1)}
                      </span>
                    </td>
                    <td className="px-2 py-3 hidden sm:table-cell">
                      <div className="flex items-center gap-1 flex-wrap">
                        {(inc.soc_criteria ?? []).slice(0, 2).map(c => (
                          <span
                            key={c}
                            className="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 text-indigo-700 text-xs font-mono font-bold px-1.5 py-0.5 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-500/20"
                          >
                            {c}
                          </span>
                        ))}
                        {(inc.soc_criteria ?? []).length > 2 && (
                          <span className="text-xs text-gray-500">
                            +{inc.soc_criteria.length - 2}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-3">
                      <span className={`inline-flex items-center rounded-full border text-xs font-medium px-2 py-0.5 ${statusBadge[inc.alert_status] ?? 'bg-gray-100 border-gray-200 text-gray-600'}`}>
                        {statusLabel[inc.alert_status] ?? inc.alert_status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-500 dark:text-gray-400 font-mono text-right whitespace-nowrap hidden md:table-cell">
                      {inc.detected_at?.slice(0, 10) ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Needs your attention */}
        <div className="lg:col-span-4 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900 overflow-hidden">
          <div className="px-6 pt-5 pb-3 flex items-center justify-between border-b border-gray-100 dark:border-gray-800">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Needs your attention
            </h2>
            {totalNeedsAttention > 0 && (
              <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 text-amber-700 text-xs font-medium px-2 py-0.5 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20">
                {totalNeedsAttention} items
              </span>
            )}
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {needsAttention.length === 0 ? (
              <div className="px-6 py-8 text-sm text-gray-400 dark:text-gray-500 text-center">
                All controls are audit-ready.
              </div>
            ) : (
              needsAttention.map(c => (
                <button
                  key={c.id}
                  onClick={() => router.push(`/controls?openControl=${c.id}`)}
                  className="w-full px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 flex items-center gap-3 text-left"
                >
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${bucketDot[c.audit_bucket] ?? 'bg-gray-400'}`} />
                  <ControlIdBadge id={c.control_id} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-900 dark:text-gray-100 truncate">{c.title}</div>
                    {c.next_action && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {c.next_action}
                      </div>
                    )}
                  </div>
                  <ChevronRight />
                </button>
              ))
            )}
          </div>
          {totalNeedsAttention > 0 && (
            <div className="border-t border-gray-100 dark:border-gray-800 px-6 py-3">
              <button
                onClick={() => router.push('/controls?evidenceStatus=not_started,pending,improvements')}
                className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium"
              >
                View all {totalNeedsAttention} items →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
