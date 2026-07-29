'use client'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRoot,
  TableRow,
} from "@/components/Table"
import { Button } from "@/components/Button"
import {
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  flexRender,
  SortingState,
  ColumnFiltersState,
} from "@tanstack/react-table"
import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { api } from '@/lib/api'
import { createColumns } from './columns'
import ControlDrawer from './ControlDrawer'
import AddControlModal from './AddControlModal'
import { ControlsFilterbar, ActiveFilters } from './ControlsFilterbar'
import { TabNavigation, TabNavigationLink } from '@/components/TabNavigation'

// ─── Types ────────────────────────────────────────────────────────────────────

export type Control = {
  id: number
  control_id: string
  title: string
  description: string
  control_type: string
  status: string
  owner: string
  tsc_criteria: string[]
  notes: string
  frequency: string | null
  requires_population: boolean
  requires_sample: boolean
  suggested_sample_size: number | null
  narrative: string | null
  updated_at: string
  evidence_count: number
  worst_verdict: string | null
  phases_present: string[]
  last_evidence_at: string | null
  audit_bucket: 'audit_ready' | 'at_risk' | 'blocked' | 'no_evidence'
  next_action: string | null
}

export type PhaseTab = 'all' | 'walkthrough' | 'population' | 'testing'

export type EvidenceStatus = 'not_started' | 'pending' | 'sufficient' | 'improvements'

// ─── Config ───────────────────────────────────────────────────────────────────

const PHASE_TABS: { key: PhaseTab; label: string; hint: string }[] = [
  { key: 'all',         label: 'All Controls',    hint: 'Full inventory with overall evidence health' },
  { key: 'walkthrough', label: 'Walkthrough',      hint: 'Design & process evidence — proves the control exists' },
  { key: 'population',  label: 'Population & IPE', hint: 'Population exports and IPE validation, cross-referenced by AI' },
  { key: 'testing',     label: 'Testing',          hint: "Sample items with results — the auditor's primary testing evidence" },
]

const PHASE_KEYS: Record<PhaseTab, string[]> = {
  all:         [],
  walkthrough: ['walkthrough'],
  population:  ['testing_population', 'testing_ipe'],
  testing:     ['testing_sample'],
}

export const EVIDENCE_STATUS_CONFIG: Record<EvidenceStatus, {
  label: string; dot: string; badge: 'default' | 'neutral' | 'success' | 'warning'
}> = {
  not_started:  { label: 'No evidence',              dot: 'bg-gray-300',    badge: 'neutral'  },
  pending:      { label: 'Pending Evaluation',       dot: 'bg-indigo-400',  badge: 'default'  },
  sufficient:   { label: 'Audit ready',              dot: 'bg-emerald-500', badge: 'success'  },
  improvements: { label: 'Improvements Recommended', dot: 'bg-amber-400',   badge: 'warning'  },
}

const TSC_LABELS: Record<string, string> = {
  CC1: 'Control Environment',
  CC2: 'Communication & Information',
  CC3: 'Risk Assessment',
  CC4: 'Monitoring Activities',
  CC5: 'Control Activities',
  CC6: 'Logical & Physical Access',
  CC7: 'System Operations',
  CC8: 'Change Management',
  CC9: 'Risk Mitigation',
  A1:  'Availability',
  PI1: 'Processing Integrity',
  C1:  'Confidentiality',
  P1: 'Privacy',
}

const CATEGORY_ORDER = [
  'CC1','CC2','CC3','CC4','CC5','CC6','CC7','CC8','CC9',
  'A1','PI1','C1','P1',
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getTscCategories(criteria: string[]): string[] {
  if (!criteria?.length) return ['Uncategorized']
  const cats = criteria
    .map(c => { const m = c.match(/^([A-Z]+\d*)/); return m ? m[1] : null })
    .filter((c): c is string => c !== null)
  return cats.length ? [...new Set(cats)] : ['Uncategorized']
}

export function getPhaseStatus(control: Control, tab: PhaseTab): EvidenceStatus {
  if (tab === 'all') {
    if (control.audit_bucket === 'no_evidence') return 'not_started'
    if (!control.worst_verdict)                 return 'pending'
    if (control.audit_bucket === 'audit_ready') return 'sufficient'
    return 'improvements'
  }
  const keys        = PHASE_KEYS[tab]
  const hasEvidence = keys.some(k => control.phases_present.includes(k))
  if (!hasEvidence)                           return 'not_started'
  if (!control.worst_verdict)                 return 'pending'
  if (control.audit_bucket === 'audit_ready') return 'sufficient'
  return 'improvements'
}

function groupByCategory(controls: Control[]) {
  const groups: Record<string, Control[]> = {}
  for (const c of controls) {
    for (const cat of getTscCategories(c.tsc_criteria)) {
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(c)
    }
  }
  return groups
}

// Normalize control_type to match filter option values
function normalizeControlType(raw: string): string {
  if (raw === 'it_dependent_manual') return 'itdm'
  return raw
}

// Maps TSC scope names → category group prefixes
const TSC_SCOPE_TO_CATEGORIES: Record<string, string[]> = {
  'Security':             ['CC1','CC2','CC3','CC4','CC5','CC6','CC7','CC8','CC9'],
  'Availability':         ['A1'],
  'Processing Integrity': ['PI1'],
  'Confidentiality':      ['C1'],
  'Privacy':              ['P1'],
}

function getScopedCategories(scope: string[]): string[] {
  return scope.flatMap(s => TSC_SCOPE_TO_CATEGORIES[s] ?? [])
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function ControlsPageContent() {
  const [orgSettings, setOrgSettings] = useState<{
    tsc_scope: string[]
    examination_type: string
  }>({ tsc_scope: ['Security'], examination_type: 'type2' })
  const [controls,        setControls]        = useState<Control[]>([])
  const [loading,         setLoading]         = useState(true)
  const [error,           setError]           = useState('')
  const [activeTab,       setActiveTab]       = useState<PhaseTab>('all')
  const [hideCompleted,   setHideCompleted]   = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const [selectedControl, setSelectedControl] = useState<Control | null>(null)
  const [addControlOpen,  setAddControlOpen]  = useState(false)
  const [sorting,         setSorting]         = useState<SortingState>([])
  const [columnFilters,   setColumnFilters]   = useState<ColumnFiltersState>([])
  const [globalFilter,    setGlobalFilter]    = useState('')
  const searchParams = useSearchParams()
  const [activeFilters,   setActiveFilters]   = useState<ActiveFilters>(() => {
    const ev = searchParams.get('evidenceStatus')
    return {
      evidenceStatus: ev ? ev.split(',') : [],
      controlType: [],
    }
  })

  const loadControls = useCallback((silent = false) => {
    if (!silent) setLoading(true)
    api.get('controls')
      .then(data => {
        const items: Control[] = Array.isArray(data) ? data : (data.items ?? [])
        setControls(items)
        const openId = searchParams.get('openControl')
        if (openId) {
          const match = items.find(c => String(c.id) === openId)
          if (match) setSelectedControl(match)
        }
      })
      .catch(e  => { if (!silent) setError(e.message) })
      .finally(() => { if (!silent) setLoading(false) })
  }, [searchParams])

  useEffect(() => { loadControls() }, [loadControls])

  useEffect(() => {
    api.get('org/settings')
      .then(data => setOrgSettings(data))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!controls.length && !orgSettings.tsc_scope) return
    const scoped = getScopedCategories(orgSettings.tsc_scope)
    const grouped = groupByCategory(controls)
    // Collapse only categories that have no controls
    const emptyCats = scoped.filter(cat => !grouped[cat] || grouped[cat].length === 0)
    setCollapsedGroups(new Set(emptyCats))
  }, [controls, orgSettings.tsc_scope])

  useEffect(() => {
    if (orgSettings.examination_type === 'type1' && activeTab === 'testing') {
      setActiveTab('all')
    }
  }, [orgSettings.examination_type])

  const columns = useMemo(
    () => createColumns(activeTab, setSelectedControl),
    [activeTab],
  )

  const table = useReactTable({
    data:    controls,
    columns,
    state:   { sorting, columnFilters, globalFilter },
    onSortingChange:       setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange:  setGlobalFilter,
    getCoreRowModel:       getCoreRowModel(),
    getFilteredRowModel:   getFilteredRowModel(),
    getSortedRowModel:     getSortedRowModel(),
  })

  // TanStack-filtered rows (global search)
  let processed = table.getRowModel().rows.map(r => r.original)

  // Apply column-level chip filters on top
  if (activeFilters.evidenceStatus.length > 0) {
    processed = processed.filter(c =>
      activeFilters.evidenceStatus.includes(getPhaseStatus(c, activeTab))
    )
  }
  if (activeFilters.controlType.length > 0) {
    processed = processed.filter(c =>
      activeFilters.controlType.includes(normalizeControlType(c.control_type))
    )
  }

  // Hide-completed toggle
  const displayed = hideCompleted && activeTab !== 'all'
    ? processed.filter(c => getPhaseStatus(c, activeTab) !== 'sufficient')
    : processed

  const scopedCats = getScopedCategories(orgSettings.tsc_scope)

  // Merge: scoped categories always appear, controls fall into them
  const grouped = groupByCategory(displayed)
  const sortedCats = [
    ...scopedCats,
    ...Object.keys(grouped).filter(c => !scopedCats.includes(c)),
  ].filter((c, i, arr) => arr.indexOf(c) === i)
    .sort((a, b) => {
      const ai = CATEGORY_ORDER.indexOf(a)
      const bi = CATEGORY_ORDER.indexOf(b)
      if (ai === -1 && bi === -1) return a.localeCompare(b)
      if (ai === -1) return 1
      if (bi === -1) return -1
      return ai - bi
    })

  function toggleGroup(cat: string) {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      next.has(cat) ? next.delete(cat) : next.add(cat)
      return next
    })
  }

  function handleTabChange(tab: PhaseTab) {
    setActiveTab(tab)
    setHideCompleted(false)
  }

  const activeTabCfg = PHASE_TABS.find(t => t.key === activeTab)!

  const visiblePhaseTabs = PHASE_TABS.filter(t =>
    orgSettings.examination_type === 'type1' ? t.key !== 'testing' : true
  )

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="flex items-center gap-2.5 text-gray-400 text-sm">
        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading controls…
      </div>
    </div>
  )

  if (error) return (
    <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
      {error}
    </div>
  )

  return (
    <div className="space-y-6">

      {/* ── Page header ── */}
      <div className="sm:flex sm:items-center sm:justify-between sm:space-x-10">
        <div>
          <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-50">
            Control Inventory
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {controls.length} controls across all SOC 2 Trust Service Criteria.
          </p>
        </div>
        <Button
          variant="primary"
          className="mt-4 w-full sm:mt-0 sm:w-fit"
          onClick={() => setAddControlOpen(true)}
        >
          Add control
        </Button>
      </div>

      {/* ── Main table card ── */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800">

        {/* ── Tabs + toolbar ── */}
        <div className="border-b border-gray-200 dark:border-gray-800">

          {/* Phase tabs row */}
          <div className="flex items-center justify-between px-6 pt-4 pb-0 gap-4">
            <TabNavigation className="border-b-0">
              {visiblePhaseTabs.map(tab => (
                <TabNavigationLink
                  key={tab.key}
                  active={activeTab === tab.key}
                  title={tab.hint}
                  onClick={() => handleTabChange(tab.key)}
                  className="cursor-pointer"
                >
                  {tab.label}
                </TabNavigationLink>
              ))}
            </TabNavigation>

            {/* Hide completed toggle (phase-specific only) */}
            {activeTab !== 'all' && (
              <label className="flex items-center gap-2 cursor-pointer select-none shrink-0 pb-2">
                <button
                  role="switch"
                  aria-checked={hideCompleted}
                  onClick={() => setHideCompleted(v => !v)}
                  className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full
                    transition-colors ${hideCompleted ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
                >
                  <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow
                    transition-transform ${hideCompleted ? 'translate-x-4' : 'translate-x-0.5'}`}
                  />
                </button>
                <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                  Hide completed
                </span>
              </label>
            )}
          </div>

          {/* Filterbar row */}
          <div className="px-6 py-3 border-t border-gray-100 dark:border-gray-800">
            <ControlsFilterbar
              filters={activeFilters}
              onChange={setActiveFilters}
              globalFilter={globalFilter}
              onGlobalFilterChange={setGlobalFilter}
            />
          </div>

          {/* Phase hint bar */}
          {activeTab !== 'all' && (
            <div className="flex items-center gap-1.5 px-6 py-2
              bg-indigo-50/60 dark:bg-indigo-500/10
              border-t border-indigo-100 dark:border-indigo-500/20">
              <svg className="w-3.5 h-3.5 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs text-indigo-600 dark:text-indigo-400">{activeTabCfg.hint}</p>
            </div>
          )}
        </div>

        {/* ── Table ── */}
        <TableRoot>
          <Table>
            <TableHead>
              {table.getHeaderGroups().map(hg => (
                <TableRow key={hg.id}>
                  {hg.headers.map(header => (
                    <TableHeaderCell
                      key={header.id}
                      className={header.column.columnDef.meta?.className}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHeaderCell>
                  ))}
                </TableRow>
              ))}
            </TableHead>

            <TableBody>
              {sortedCats.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={columns.length} className="h-24 text-center text-sm text-gray-400">
                    No controls match your current filters.
                  </TableCell>
                </TableRow>
              ) : (
                sortedCats.map(cat => {
                  const items     = grouped[cat] ?? [] 
                  const collapsed = collapsedGroups.has(cat)
                  const completed = activeTab === 'all'
                    ? items.filter(c => c.audit_bucket === 'audit_ready').length
                    : items.filter(c => getPhaseStatus(c, activeTab) === 'sufficient').length
                  const pct     = items.length ? (completed / items.length) * 100 : 0
                  const allDone = completed === items.length

                  return (
                    <React.Fragment key={cat}>

                      {/* Group header */}
                      <TableRow
                        className="bg-gray-50 dark:bg-gray-800/60
                          hover:bg-gray-100 dark:hover:bg-gray-800
                          cursor-pointer select-none
                          border-y border-gray-200 dark:border-gray-700"
                        onClick={() => toggleGroup(cat)}
                      >
                        <TableCell colSpan={columns.length} className="py-2.5 px-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                              <svg
                                className={`w-3 h-3 text-gray-400 transition-transform duration-150
                                  ${collapsed ? '-rotate-90' : ''}`}
                                fill="none" stroke="currentColor" viewBox="0 0 24 24"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round"
                                  strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                              </svg>
                              <span className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                                {cat}
                              </span>
                              <span className="text-xs text-gray-400 dark:text-gray-500 hidden sm:inline">
                                {TSC_LABELS[cat] ?? ''}
                              </span>
                              <span className="text-[10px] font-semibold
                                text-gray-500 dark:text-gray-400
                                bg-gray-200 dark:bg-gray-700
                                px-1.5 py-0.5 rounded-full">
                                {items.length}
                              </span>
                            </div>
                            <div className="flex items-center gap-2.5">
                              <span className={`text-xs font-medium ${
                                allDone
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : 'text-gray-400 dark:text-gray-500'
                              }`}>
                                {completed}/{items.length} {activeTab === 'all' ? 'audit ready' : 'complete'}
                              </span>
                              <div className="w-24 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-300 ${
                                    allDone ? 'bg-emerald-500' : 'bg-indigo-400'
                                  }`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>

                      {/* Control rows */}
                      {!collapsed && items.map(control => {
                        const row = table.getRowModel().rows.find(r => r.original.id === control.id)
                        if (!row) return null
                        return (
                          <TableRow
                            key={control.id}
                            onClick={() => setSelectedControl(control)}
                            className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer select-none"
                          >
                            {row.getVisibleCells().map(cell => (
                              <TableCell
                                key={cell.id}
                                className={cell.column.columnDef.meta?.className}
                              >
                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                              </TableCell>
                            ))}
                          </TableRow>
                        )
                      })}

                      {!collapsed && items.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={columns.length} className="py-6 px-6">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-800
                                  flex items-center justify-center shrink-0">
                                  <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
                                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                </div>
                                <div>
                                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                                    No controls tagged to this criteria
                                  </p>
                                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                                    Add a control and tag it to this category to begin tracking coverage.
                                  </p>
                                </div>
                              </div>
                              <button
                                onClick={() => setAddControlOpen(true)}
                                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg
                                  text-indigo-600 dark:text-indigo-400
                                  bg-indigo-50 dark:bg-indigo-500/10
                                  hover:bg-indigo-100 dark:hover:bg-indigo-500/20
                                  border border-indigo-200 dark:border-indigo-500/30
                                  transition-colors shrink-0"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                                Add control
                              </button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  )
                })
              )}
            </TableBody>
          </Table>
        </TableRoot>

        {/* ── Footer ── */}
        <div className="px-6 py-3 border-t border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <p className="text-xs text-gray-400 dark:text-gray-500">
            {displayed.length} of {controls.length} controls
            {globalFilter && <span> · &ldquo;{globalFilter}&rdquo;</span>}
            {hideCompleted && <span> · hiding completed</span>}
            {(activeFilters.evidenceStatus.length > 0 || activeFilters.controlType.length > 0) && (
              <span> · filtered</span>
            )}
          </p>
          {(globalFilter || activeFilters.evidenceStatus.length > 0 || activeFilters.controlType.length > 0) && (
            <button
              onClick={() => {
                setGlobalFilter('')
                setActiveFilters({ evidenceStatus: [], controlType: [] })
              }}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {/* ── Drawer ── */}
      {selectedControl && (
        <ControlDrawer
          control={selectedControl}
          defaultPhase={activeTab === 'all' ? 'walkthrough' : activeTab}
          onClose={() => setSelectedControl(null)}
          onRefresh={() => loadControls(true)}
        />
      )}

      {/* ── Add control modal ── */}
      <AddControlModal
        open={addControlOpen}
        onOpenChange={setAddControlOpen}
        orgScope={orgSettings.tsc_scope}
        onCreated={() => loadControls(true)}
      />
    </div>
  )
}

export default function ControlsPage() {
  return (
    <Suspense fallback={null}>
      <ControlsPageContent />
    </Suspense>
  )
}