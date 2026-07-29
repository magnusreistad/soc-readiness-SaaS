'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { Button } from '@/components/Button'
import { Input } from '@/components/Input'
import { Label } from '@/components/Label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/Select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/Dialog'
import { TabNavigation, TabNavigationLink } from '@/components/TabNavigation'
import { Control, PhaseTab } from './page'

// ─── Types ────────────────────────────────────────────────────────────────────

type EvaluationResult = {
  verdict: 'ready_to_submit' | 'needs_work' | 'do_not_submit'
  rejection_risk: 'low' | 'medium' | 'high'
  rejection_risk_reason: string
  phase: string
  satisfied_attributes: string[]
  gap_attributes: string[]
  what_to_fix: string[]
  evidence_quality: string
  auditor_notes: string
  pii_redacted: boolean
  was_truncated: boolean
}

type EvidenceFile = {
  id: number
  control_id: number
  phase: string
  phase_label: string
  filename: string
  file_type: string
  evaluation: EvaluationResult | null
  uploaded_by: string | null
  uploaded_at: string
  evaluated_at: string | null
}

type EvidenceByPhase = {
  walkthrough: EvidenceFile[]
  testing_population: EvidenceFile[]
  testing_ipe: EvidenceFile[]
  testing_sample: EvidenceFile[]
  package_status: string
  package_summary: string
}

type DrawerPhase = 'walkthrough' | 'population' | 'testing'

// ─── Static config ────────────────────────────────────────────────────────────

const DRAWER_PHASES: {
  key: DrawerPhase
  label: string
  apiKeys: string[]
  description: string
  acceptMultiple: boolean
  hint: string
}[] = [
  {
    key:            'walkthrough',
    label:          'Walkthrough',
    apiKeys:        ['walkthrough'],
    description:    'Proves the control exists and is suitably designed. Point-in-time evidence.',
    acceptMultiple: false,
    hint:           'Policy documents, process walkthroughs, screenshots, meeting notes',
  },
  {
    key:            'population',
    label:          'Population & IPE',
    apiKeys:        ['testing_population', 'testing_ipe'],
    description:    'Upload the population export and IPE validation together. AI cross-references record counts, date ranges, and source system names.',
    acceptMultiple: true,
    hint:           'Population export (system report) + IPE validation document',
  },
  {
    key:            'testing',
    label:          'Testing',
    apiKeys:        ['testing_sample'],
    description:    'Sample items with evidence of control operation. Contemporaneous evidence of what the auditor will test.',
    acceptMultiple: true,
    hint:           'Approval emails, screenshots, access logs, signed forms — one per sample item',
  },
]

export const CONTROL_TYPE_OPTIONS = [
  { value: 'manual',    label: 'Manual' },
  { value: 'automated', label: 'Automated' },
  { value: 'itdm',      label: 'IT Dependent Manual (ITDM)' },
]

export const FREQUENCY_OPTIONS = [
  { value: 'annual',      label: 'Annual' },
  { value: 'semi_annual', label: 'Semi-Annual' },
  { value: 'quarterly',   label: 'Quarterly' },
  { value: 'monthly',     label: 'Monthly' },
  { value: 'weekly',      label: 'Weekly' },
  { value: 'daily',       label: 'Daily' },
  { value: 'continuous',  label: 'Continuous' },
  { value: 'adhoc',       label: 'Ad hoc / As needed' },
]

const CONTROL_TYPE_LABELS: Record<string, string> = {
  automated:           'Automated',
  manual:              'Manual',
  it_dependent_manual: 'IT Dependent Manual',
  itdm:                'IT Dependent Manual',
}

const FREQUENCY_LABELS: Record<string, string> = {
  annual:      'Annual',      semi_annual: 'Semi-Annual',
  quarterly:   'Quarterly',   monthly:     'Monthly',
  weekly:      'Weekly',      daily:       'Daily',
  continuous:  'Continuous',  adhoc:       'Ad hoc',
}

// Mirrors TSC_CATEGORIES from app/utils/soc_mapper.py
// grouped for display — Security always shown, others shown when in org scope
const TSC_CRITERIA_GROUPS: Record<string, { group: string; codes: string[] }[]> = {
  Security: [
    { group: 'CC1 — Control Environment',            codes: ['CC1.1','CC1.2','CC1.3','CC1.4','CC1.5'] },
    { group: 'CC2 — Communication & Information',    codes: ['CC2.1','CC2.2','CC2.3'] },
    { group: 'CC3 — Risk Assessment',                codes: ['CC3.1','CC3.2','CC3.3','CC3.4'] },
    { group: 'CC4 — Monitoring Activities',          codes: ['CC4.1','CC4.2'] },
    { group: 'CC5 — Control Activities',             codes: ['CC5.1','CC5.2','CC5.3'] },
    { group: 'CC6 — Logical & Physical Access',      codes: ['CC6.1','CC6.2','CC6.3','CC6.4','CC6.5','CC6.6','CC6.7','CC6.8'] },
    { group: 'CC7 — System Operations',              codes: ['CC7.1','CC7.2','CC7.3','CC7.4','CC7.5'] },
    { group: 'CC8 — Change Management',              codes: ['CC8.1'] },
    { group: 'CC9 — Risk Mitigation',                codes: ['CC9.1','CC9.2'] },
  ],
  Availability: [
    { group: 'A1 — Availability',                   codes: ['A1.1','A1.2','A1.3'] },
  ],
  Confidentiality: [
    { group: 'C1 — Confidentiality',                codes: ['C1.1','C1.2'] },
  ],
  'Processing Integrity': [
    { group: 'PI1 — Processing Integrity',           codes: ['PI1.1','PI1.2','PI1.3','PI1.4','PI1.5'] },
  ],
  Privacy: [
    { group: 'P — Privacy',                          codes: ['P1.1','P2.1','P3.1','P3.2','P4.1','P4.2','P4.3','P5.1','P5.2','P6.1','P6.2','P6.3','P6.4','P6.5','P6.6','P6.7','P7.1','P8.1'] },
  ],
}

const VERDICT_CONFIG = {
  ready_to_submit: {
    label: 'Ready to Submit', icon: '✓',
    bg: 'bg-emerald-50', darkBg: 'dark:bg-emerald-500/10',
    border: 'border-emerald-200', darkBorder: 'dark:border-emerald-500/30',
    iconCls: 'text-emerald-600 bg-emerald-100', darkIconCls: 'dark:text-emerald-400 dark:bg-emerald-500/20',
    text: 'text-emerald-900', darkText: 'dark:text-emerald-300',
    badgeCls: 'bg-emerald-100 text-emerald-700', darkBadgeCls: 'dark:bg-emerald-500/20 dark:text-emerald-400',
  },
  needs_work: {
    label: 'Needs Work', icon: '!',
    bg: 'bg-amber-50', darkBg: 'dark:bg-amber-500/10',
    border: 'border-amber-200', darkBorder: 'dark:border-amber-500/30',
    iconCls: 'text-amber-600 bg-amber-100', darkIconCls: 'dark:text-amber-400 dark:bg-amber-500/20',
    text: 'text-amber-900', darkText: 'dark:text-amber-300',
    badgeCls: 'bg-amber-100 text-amber-700', darkBadgeCls: 'dark:bg-amber-500/20 dark:text-amber-400',
  },
  do_not_submit: {
    label: 'Do Not Submit', icon: '✕',
    bg: 'bg-red-50', darkBg: 'dark:bg-red-500/10',
    border: 'border-red-200', darkBorder: 'dark:border-red-500/30',
    iconCls: 'text-red-600 bg-red-100', darkIconCls: 'dark:text-red-400 dark:bg-red-500/20',
    text: 'text-red-900', darkText: 'dark:text-red-300',
    badgeCls: 'bg-red-100 text-red-700', darkBadgeCls: 'dark:bg-red-500/20 dark:text-red-400',
  },
}

const PHASE_STATUS_DOT: Record<string, string> = {
  not_started:  'bg-gray-300',
  pending:      'bg-amber-400',
  sufficient:   'bg-emerald-500',
  improvements: 'bg-orange-400',
}

// ─── Criteria picker sub-component ───────────────────────────────────────────

export function CriteriaPicker({
  selected,
  onChange,
  orgScope,
}: {
  selected: string[]
  onChange: (codes: string[]) => void
  orgScope: string[]
}) {
  // Always include Security; add others based on org scope
  const activeScopes = ['Security', ...orgScope.filter(s => s !== 'Security')]
  const groups = activeScopes.flatMap(scope => TSC_CRITERIA_GROUPS[scope] ?? [])

  function toggle(code: string) {
    onChange(
      selected.includes(code)
        ? selected.filter(c => c !== code)
        : [...selected, code]
    )
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      {/* Selected summary */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        {selected.length === 0 ? (
          <span className="text-xs text-gray-400 dark:text-gray-500">No criteria selected</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {selected.map(code => (
              <span
                key={code}
                onClick={() => toggle(code)}
                className="inline-flex items-center gap-1 text-xs font-mono font-medium px-1.5 py-0.5 rounded
                  bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300
                  cursor-pointer hover:bg-red-100 dark:hover:bg-red-500/20
                  hover:text-red-600 dark:hover:text-red-400 transition-colors"
                title="Click to remove"
              >
                {code} ×
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Scrollable criteria list */}
      <div className="max-h-52 overflow-y-auto p-3 space-y-4">
        {groups.map(({ group, codes }) => (
          <div key={group}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-1.5">
              {group}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {codes.map(code => {
                const isSelected = selected.includes(code)
                return (
                  <button
                    key={code}
                    onClick={() => toggle(code)}
                    type="button"
                    className={`text-xs font-mono px-2 py-0.5 rounded border transition-colors ${
                      isSelected
                        ? 'bg-indigo-600 border-indigo-600 text-white dark:bg-indigo-500 dark:border-indigo-500'
                        : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-indigo-300 dark:hover:border-indigo-600'
                    }`}
                  >
                    {code}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── EvaluationCard ───────────────────────────────────────────────────────────

function EvaluationCard({ eval: ev }: { eval: EvaluationResult }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = VERDICT_CONFIG[ev.verdict] ?? VERDICT_CONFIG.do_not_submit

  return (
    <div className={`rounded-lg border p-3 ${cfg.bg} ${cfg.border} ${cfg.darkBg} ${cfg.darkBorder}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${cfg.iconCls} ${cfg.darkIconCls}`}>
            {cfg.icon}
          </span>
          <span className={`text-xs font-semibold ${cfg.text} ${cfg.darkText}`}>{cfg.label}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full capitalize ${cfg.badgeCls} ${cfg.darkBadgeCls}`}>
            {ev.rejection_risk} risk
          </span>
          {(ev.what_to_fix?.length > 0 || ev.gap_attributes?.length > 0) && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="text-[10px] font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
            >
              {expanded ? 'Less' : 'Details'}
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-3 pt-3 border-t border-black/10 dark:border-white/10">
          {ev.what_to_fix?.length > 0 && (
            <div>
              <p className={`text-[10px] font-semibold uppercase tracking-wide mb-1.5 ${cfg.text} ${cfg.darkText}`}>What to fix</p>
              <ol className="space-y-1">
                {ev.what_to_fix.map((item, i) => (
                  <li key={i} className={`text-xs flex gap-1.5 ${cfg.text} ${cfg.darkText}`}>
                    <span className="shrink-0 font-bold opacity-50">{i + 1}.</span>{item}
                  </li>
                ))}
              </ol>
            </div>
          )}
          {ev.gap_attributes?.length > 0 && (
            <div>
              <p className={`text-[10px] font-semibold uppercase tracking-wide mb-1.5 ${cfg.text} ${cfg.darkText}`}>Gaps</p>
              <ul className="space-y-1">
                {ev.gap_attributes.map((gap, i) => (
                  <li key={i} className={`text-xs flex gap-1.5 ${cfg.text} ${cfg.darkText}`}>
                    <span className="shrink-0 opacity-50">·</span>{gap}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ev.auditor_notes && (
            <p className={`text-xs italic opacity-70 ${cfg.text} ${cfg.darkText}`}>{ev.auditor_notes}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── EvidenceFileRow ──────────────────────────────────────────────────────────

function EvidenceFileRow({
  file,
  controlId,
  onDelete,
}: {
  file: EvidenceFile
  controlId: number
  onDelete: (id: number) => void
}) {
  const [deleting,     setDeleting]     = useState(false)
  const [confirmDel,   setConfirmDel]   = useState(false)
  const [reEvaluating, setReEvaluating] = useState(false)
  const [localFile,    setLocalFile]    = useState(file)

  async function handleDelete() {
    if (!confirmDel) { setConfirmDel(true); return }
    setDeleting(true)
    try {
      await api.delete(`controls/${controlId}/evidence/${file.id}`)
      onDelete(file.id)
    } catch { setDeleting(false); setConfirmDel(false) }
  }

  async function handleReEvaluate() {
    setReEvaluating(true)
    try {
      const updated = await api.post(`controls/${controlId}/evidence/${file.id}/re-evaluate`, {})
      setLocalFile(updated)
    } catch { /* ignore */ } finally { setReEvaluating(false) }
  }

  const ext = localFile.filename.split('.').pop()?.toUpperCase() ?? 'FILE'

  return (
    <div className="group space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
            {ext}
          </span>
          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">{localFile.filename}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleReEvaluate}
            disabled={reEvaluating}
            className="text-xs text-indigo-500 hover:text-indigo-700 dark:text-indigo-400 disabled:opacity-50 transition-colors opacity-0 group-hover:opacity-100"
          >
            {reEvaluating ? 'Re-evaluating…' : 'Re-evaluate'}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className={`text-xs transition-colors disabled:opacity-50 ${
              confirmDel
                ? 'text-red-600 dark:text-red-400 font-medium'
                : 'text-gray-300 dark:text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100'
            }`}
          >
            {deleting ? '…' : confirmDel ? 'Confirm?' : 'Remove'}
          </button>
        </div>
      </div>
      {localFile.evaluation ? (
        <EvaluationCard eval={localFile.evaluation} />
      ) : (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
          <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
          <span className="text-xs text-gray-500 dark:text-gray-400">Pending evaluation</span>
        </div>
      )}
    </div>
  )
}

// ─── UploadZone ───────────────────────────────────────────────────────────────

function UploadZone({
  controlId, phaseApiKey, acceptMultiple, hint, criteriaCode, onUploaded,
}: {
  controlId: number; phaseApiKey: string; acceptMultiple: boolean
  hint: string; criteriaCode: string; onUploaded: () => void
}) {
  const inputRef            = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error,     setError]     = useState('')
  const [dragging,  setDragging]  = useState(false)

  async function uploadFiles(files: File[]) {
    if (!files.length) return
    setError(''); setUploading(true)
    try {
      for (const file of files) {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('phase', phaseApiKey)
        fd.append('criteria_code', criteriaCode)
        await api.upload(`controls/${controlId}/evidence`, fd)
      }
      onUploaded()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally { setUploading(false) }
  }

  return (
    <div>
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault(); setDragging(false)
          const files = Array.from(e.dataTransfer.files)
          if (files.length) uploadFiles(acceptMultiple ? files : [files[0]])
        }}
        className={`relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          dragging
            ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-500/10'
            : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-600 bg-gray-50/50 dark:bg-gray-800/50'
        }`}
      >
        <input ref={inputRef} type="file" className="hidden" multiple={acceptMultiple}
          onChange={e => {
            const files = Array.from(e.target.files ?? [])
            if (files.length) uploadFiles(acceptMultiple ? files : [files[0]])
            e.target.value = ''
          }}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <svg className="animate-spin w-6 h-6 text-indigo-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-xs text-gray-500 dark:text-gray-400">Uploading & evaluating…</p>
          </div>
        ) : (
          <>
            <svg className="w-7 h-7 mx-auto mb-2 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
              {dragging ? 'Drop to upload' : 'Drop files here or click to browse'}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{hint}</p>
            <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">PDF, Excel, Word, CSV, Images</p>
          </>
        )}
      </div>
      {error && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
          <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          {error}
        </div>
      )}
    </div>
  )
}

// ─── Main drawer ─────────────────────────────────────────────────────────────

interface ControlDrawerProps {
  control:      Control
  defaultPhase: PhaseTab
  onClose:      () => void
  onRefresh:    () => void
}

export default function ControlDrawer({ control, defaultPhase, onClose, onRefresh }: ControlDrawerProps) {
  const initialPhase: DrawerPhase =
    defaultPhase === 'population' ? 'population' :
    defaultPhase === 'testing'    ? 'testing'    : 'walkthrough'

  const [controlData, setControlData] = useState<Control>(control)
  const [activePhase, setActivePhase] = useState<DrawerPhase>(initialPhase)
  const [evidence,    setEvidence]    = useState<EvidenceByPhase | null>(null)
  const [loadingEv,   setLoadingEv]   = useState(true)
  const [evError,     setEvError]     = useState('')
  const [visible,     setVisible]     = useState(false)

  // Org scope — fetched once on mount for the criteria picker
  const [orgScope, setOrgScope] = useState<string[]>(['Security'])

  // "..." dropdown
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef                 = useRef<HTMLDivElement>(null)

  // Drawer panel ref — for click-outside-to-close
  const drawerRef = useRef<HTMLDivElement>(null)

  // Edit modal state
  const [editOpen,      setEditOpen]      = useState(false)
  const [editControlId, setEditControlId] = useState('')
  const [editDesc,      setEditDesc]      = useState('')
  const [editOwner,     setEditOwner]     = useState('')
  const [editType,      setEditType]      = useState('')
  const [editFreq,      setEditFreq]      = useState<string>('')
  const [editCriteria,  setEditCriteria]  = useState<string[]>([])
  const [saving,        setSaving]        = useState(false)
  const [saveError,     setSaveError]     = useState('')

  // Delete confirmation
  const [deleteOpen,  setDeleteOpen]  = useState(false)
  const [deleting,    setDeleting]    = useState(false)
  const [deleteError, setDeleteError] = useState('')

  // Fetch org settings for criteria scope
  useEffect(() => {
    api.get('org/settings')
      .then((data: { tsc_scope?: string[] }) => {
        setOrgScope(data.tsc_scope ?? ['Security'])
      })
      .catch(() => {})
  }, [])

  // Close menu on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  // Close drawer on outside click (without blocking page scroll)
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        handleClose()
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 10)
    return () => clearTimeout(t)
  }, [])

  const loadEvidence = useCallback(() => {
    setLoadingEv(true)
    setEvError('')
    api.get(`controls/${controlData.id}/evidence`)
      .then(setEvidence)
      .catch(e => setEvError(e.message))
      .finally(() => setLoadingEv(false))
  }, [controlData.id])

  useEffect(() => { loadEvidence() }, [loadEvidence])

  function handleClose() {
    setVisible(false)
    setTimeout(onClose, 300)
  }

  function handleUploaded() { loadEvidence(); onRefresh() }

  function handleDeleteFile(fileId: number) {
    setEvidence(prev => {
      if (!prev) return prev
      return {
        ...prev,
        walkthrough:        prev.walkthrough.filter(f => f.id !== fileId),
        testing_population: prev.testing_population.filter(f => f.id !== fileId),
        testing_ipe:        prev.testing_ipe.filter(f => f.id !== fileId),
        testing_sample:     prev.testing_sample.filter(f => f.id !== fileId),
      }
    })
    onRefresh()
  }

  function openEditModal() {
    setEditControlId(controlData.control_id ?? '')
    setEditDesc(controlData.description ?? '')
    setEditOwner(controlData.owner ?? '')
    setEditType(controlData.control_type ?? 'manual')
    setEditFreq(controlData.frequency ?? '')
    setEditCriteria(Array.isArray(controlData.tsc_criteria) ? [...controlData.tsc_criteria] : [])
    setSaveError('')
    setMenuOpen(false)
    setEditOpen(true)
  }

  async function handleSaveEdit() {
    setSaving(true)
    setSaveError('')
    try {
      const payload = {
        control_id:   editControlId.trim() || undefined,
        description:  editDesc,
        owner:        editOwner,
        control_type: editType,
        frequency:    (editFreq && editFreq !== 'none') ? editFreq : null,
        tsc_criteria: editCriteria,
      }

      await api.patch(`controls/${controlData.id}`, payload)

      // Update directly from form values — no dependency on API response format
      setControlData(prev => ({
        ...prev,
        control_id:   editControlId.trim() || prev.control_id,
        description:  editDesc,
        owner:        editOwner,
        control_type: editType,
        frequency:    payload.frequency,
        tsc_criteria: editCriteria,
      }))
      setEditOpen(false)
      onRefresh()
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Save failed. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setDeleteError('')
    try {
      await api.delete(`controls/${controlData.id}`)
      setDeleteOpen(false)
      handleClose()
      onRefresh()
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Delete failed.')
      setDeleting(false)
    }
  }

  function phaseTabStatus(p: DrawerPhase): 'not_started' | 'pending' | 'sufficient' | 'improvements' | null {
    if (!evidence) return null
    const cfg   = DRAWER_PHASES.find(x => x.key === p)!
    const files = cfg.apiKeys.flatMap(k => evidence[k as keyof EvidenceByPhase] as EvidenceFile[])
    if (!files.length) return 'not_started'
    if (files.every(f => f.evaluation?.verdict === 'ready_to_submit')) return 'sufficient'
    if (files.some(f => f.evaluation?.verdict === 'do_not_submit'))    return 'improvements'
    if (files.some(f => f.evaluation?.verdict === 'needs_work'))       return 'improvements'
    return 'pending'
  }

  const phaseCfg   = DRAWER_PHASES.find(p => p.key === activePhase)!
  const phaseFiles = phaseCfg.apiKeys.flatMap(k =>
    evidence ? (evidence[k as keyof EvidenceByPhase] as EvidenceFile[]) : []
  )

  // Overall evidence status for footer
  const overallStatus = (() => {
    if (!evidence) return { dot: 'not_started', label: 'Loading…' }
    const all = [
      ...evidence.walkthrough, ...evidence.testing_population,
      ...evidence.testing_ipe, ...evidence.testing_sample,
    ]
    if (!all.length)                                                      return { dot: 'not_started',  label: 'No evidence uploaded' }
    if (all.every(f => f.evaluation?.verdict === 'ready_to_submit'))      return { dot: 'sufficient',   label: 'All evidence ready' }
    if (all.some(f => f.evaluation?.verdict === 'do_not_submit'))         return { dot: 'improvements', label: 'Issues require attention' }
    if (all.some(f => f.evaluation?.verdict === 'needs_work'))            return { dot: 'improvements', label: 'Improvements recommended' }
    return { dot: 'pending', label: `${all.length} file${all.length !== 1 ? 's' : ''} uploaded` }
  })()

  return (
    <>
      {/* Drawer panel */}
      <div ref={drawerRef} className={`fixed right-0 top-0 h-[100dvh] w-[520px] max-w-full z-50 flex flex-col
        bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800
        shadow-2xl transition-transform duration-300 ease-in-out
        ${visible ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* ── Header ── */}
        <div className="flex items-start justify-between px-6 py-5 shrink-0 border-b border-gray-100 dark:border-gray-800">
          <div className="min-w-0 pr-3">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded
                text-indigo-600 dark:text-indigo-400
                bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/30">
                {controlData.control_id}
              </span>
              {controlData.control_type && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800">
                  {CONTROL_TYPE_LABELS[controlData.control_type] ?? controlData.control_type}
                </span>
              )}
              {controlData.frequency && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800">
                  {FREQUENCY_LABELS[controlData.frequency] ?? controlData.frequency}
                </span>
              )}
            </div>
            <h2 className="text-base font-semibold leading-snug text-gray-900 dark:text-gray-50">
              {controlData.title}
            </h2>
            {controlData.description && (
              <p className="text-xs mt-1 text-gray-500 dark:text-gray-400">
                {controlData.description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* "..." menu */}
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(v => !v)}
                className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors
                  text-gray-400 hover:text-gray-600 hover:bg-gray-100
                  dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-800"
                aria-label="More options"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <circle cx="5" cy="12" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="19" cy="12" r="1.5" />
                </svg>
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-full mt-1 w-44 rounded-lg border shadow-lg py-1 z-10
                  bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700">
                  <button
                    onClick={openEditModal}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-300
                      hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-left"
                  >
                    <svg className="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Edit control
                  </button>
                  <div className="my-1 border-t border-gray-100 dark:border-gray-800" />
                  <button
                    onClick={() => { setMenuOpen(false); setDeleteError(''); setDeleteOpen(true) }}
                    className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-red-600 dark:text-red-400
                      hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors text-left"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Delete control
                  </button>
                </div>
              )}
            </div>

            {/* Close */}
            <button
              onClick={handleClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors
                text-gray-400 hover:text-gray-600 hover:bg-gray-100
                dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-800"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* ── TSC criteria chips ── */}
        {controlData.tsc_criteria?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-6 py-3 shrink-0
            border-b border-gray-100 dark:border-gray-800 bg-gray-50/40 dark:bg-gray-800/40">
            {[...controlData.tsc_criteria].sort((a, b) => {
              const parse = (s: string) => { const m = s.match(/^([A-Za-z]+)(\d+)\.(\d+)$/); return m ? [m[1], +m[2], +m[3]] as [string, number, number] : [s, 0, 0] as [string, number, number] }
              const [ap, am, as_] = parse(a); const [bp, bm, bs] = parse(b)
              return ap.localeCompare(bp) || am - bm || as_ - bs
            }).map(code => (
              <span key={code} className="text-xs font-medium px-2 py-0.5 rounded-full
                text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                {code}
              </span>
            ))}
            {controlData.owner && (
              <span className="text-xs ml-auto self-center text-gray-400 dark:text-gray-500">
                Owner: {controlData.owner}
              </span>
            )}
          </div>
        )}

        {/* ── Phase tabs ── */}
        <div className="px-6 pt-3 shrink-0 border-b border-gray-200 dark:border-gray-800">
          <TabNavigation className="border-b-0">
            {DRAWER_PHASES.map(p => {
              const status = phaseTabStatus(p.key)
              return (
                <TabNavigationLink
                  key={p.key}
                  active={activePhase === p.key}
                  onClick={() => setActivePhase(p.key)}
                  className="cursor-pointer"
                >
                  {p.label}
                  {status && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${PHASE_STATUS_DOT[status]}`} />}
                </TabNavigationLink>
              )
            })}
          </TabNavigation>
        </div>

        {/* ── Tab content ── */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-100 dark:border-blue-500/20 rounded-lg px-4 py-3">
            <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">{phaseCfg.description}</p>
          </div>


          {loadingEv ? (
            <div className="flex items-center justify-center py-10">
              <svg className="animate-spin w-5 h-5 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : evError ? (
            <div className="rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">
              {evError}
            </div>
          ) : (
            <>
              {phaseFiles.length > 0 ? (
                <div className="space-y-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                    Uploaded evidence ({phaseFiles.length})
                  </p>
                  <div className="space-y-4 divide-y divide-gray-100 dark:divide-gray-800">
                    {phaseFiles.map(f => (
                      <div key={f.id} className="pt-4 first:pt-0">
                        <EvidenceFileRow file={f} controlId={controlData.id} onDelete={handleDeleteFile} />
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center mb-3 bg-gray-100 dark:bg-gray-800">
                    <svg className="w-5 h-5 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No {phaseCfg.label} evidence uploaded</p>
                  <p className="text-xs mt-1 text-gray-400 dark:text-gray-500">Upload a file below to begin evaluation</p>
                </div>
              )}

              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-2 text-gray-400 dark:text-gray-500">
                  {phaseFiles.length > 0 ? 'Add more evidence' : 'Upload evidence'}
                </p>
                <UploadZone
                  controlId={controlData.id}
                  phaseApiKey={phaseCfg.apiKeys[0]}
                  acceptMultiple={phaseCfg.acceptMultiple}
                  hint={phaseCfg.hint}
                  criteriaCode={controlData.tsc_criteria?.[0] ?? ''}
                  onUploaded={handleUploaded}
                />
              </div>
            </>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="px-6 py-3.5 shrink-0 border-t border-gray-100 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-800/40">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${PHASE_STATUS_DOT[overallStatus.dot]}`} />
            <span className="text-xs text-gray-500 dark:text-gray-400">{overallStatus.label}</span>
          </div>
        </div>
      </div>

      {/* ══ Edit modal ══════════════════════════════════════════════════════ */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Edit control</DialogTitle>
            <DialogDescription>
              Update criteria mapping, description, owner, control type and frequency.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-5">

            {/* Control ID + Owner side by side */}
            <div>
              <Label htmlFor="edit-control-id" className="font-medium">Control ID</Label>
              <Input
                id="edit-control-id"
                type="text"
                placeholder="e.g. CC6.1-01"
                value={editControlId}
                onChange={e => setEditControlId(e.target.value)}
                className="mt-2 font-mono"
              />
            </div>
            <div>
              <Label htmlFor="edit-owner" className="font-medium">Owner</Label>
              <Input
                id="edit-owner"
                type="text"
                placeholder="Name or team responsible"
                value={editOwner}
                onChange={e => setEditOwner(e.target.value)}
                className="mt-2"
              />
            </div>

            {/* Control Type + Frequency side by side */}
            <div>
              <Label className="font-medium">Control Type</Label>
              <Select value={editType} onValueChange={setEditType}>
                <SelectTrigger className="mt-2">
                  <SelectValue placeholder="Select type…" />
                </SelectTrigger>
                <SelectContent>
                  {CONTROL_TYPE_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="font-medium">Frequency</Label>
              <Select value={editFreq || 'none'} onValueChange={v => setEditFreq(v === 'none' ? '' : v)}>
                <SelectTrigger className="mt-2">
                  <SelectValue placeholder="Not set" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— Not set —</SelectItem>
                  {FREQUENCY_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Description — full width */}
            <div className="col-span-2">
              <Label htmlFor="edit-desc" className="font-medium">Description</Label>
              <textarea
                id="edit-desc"
                rows={3}
                value={editDesc}
                onChange={e => setEditDesc(e.target.value)}
                placeholder="Describe what this control does and how it operates…"
                className="mt-2 w-full rounded-md border border-gray-300 dark:border-gray-800
                  bg-white dark:bg-gray-950 px-2.5 py-1.5 text-sm
                  text-gray-900 dark:text-gray-50
                  placeholder-gray-400 dark:placeholder-gray-500
                  focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none transition"
              />
            </div>

            {/* TSC Criteria picker — full width */}
            <div className="col-span-2">
              <Label className="font-medium">TSC Criteria</Label>
              <p className="text-xs text-gray-400 dark:text-gray-500 mb-2 mt-0.5">
                Select all criteria this control addresses. Only criteria in your org&apos;s examination scope are shown.
              </p>
              <CriteriaPicker
                selected={editCriteria}
                onChange={setEditCriteria}
                orgScope={orgScope}
              />
            </div>

            {saveError && (
              <p className="col-span-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10
                border border-red-200 dark:border-red-500/30 rounded-lg px-3 py-2">
                {saveError}
              </p>
            )}
          </div>

          <DialogFooter className="mt-6">
            <Button variant="secondary" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSaveEdit} isLoading={saving} loadingText="Saving…">
              Save changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ══ Delete confirmation ═════════════════════════════════════════════ */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-500/20 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              </div>
              <DialogTitle>Delete this control?</DialogTitle>
            </div>
            <DialogDescription>
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                {controlData.control_id} — {controlData.title}
              </span>{' '}
              and all associated evidence files will be permanently removed. This cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {deleteError && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10
              border border-red-200 dark:border-red-500/30 rounded-lg px-3 py-2">
              {deleteError}
            </p>
          )}

          <DialogFooter className="mt-6">
            <Button variant="secondary" onClick={() => setDeleteOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} isLoading={deleting} loadingText="Deleting…">
              Yes, delete control
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}