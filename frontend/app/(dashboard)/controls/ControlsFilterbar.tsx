'use client'

import { useRef, useState } from 'react'
import { RiAddLine, RiArrowDownSLine } from '@remixicon/react'
import { Searchbar } from '@/components/Searchbar'
import { cx } from '@/lib/utils'

// ─── Types ────────────────────────────────────────────────────────────────────

export type ActiveFilters = {
  evidenceStatus: string[]
  controlType: string[]
}

interface ControlsFilterbarProps {
  filters: ActiveFilters
  onChange: (filters: ActiveFilters) => void
  globalFilter: string
  onGlobalFilterChange: (value: string) => void
}

// ─── Filter options ───────────────────────────────────────────────────────────

const EVIDENCE_STATUS_OPTIONS = [
  { label: 'No evidence',              value: 'not_started'  },
  { label: 'Pending Evaluation',       value: 'pending'      },
  { label: 'Audit ready',              value: 'sufficient'   },
  { label: 'Improvements Recommended', value: 'improvements' },
]

const CONTROL_TYPE_OPTIONS = [
  { label: 'Automated',            value: 'automated' },
  { label: 'Manual',               value: 'manual'    },
  { label: 'IT Dependent Manual',  value: 'itdm'      },
]

// ─── Single filter chip with popover ─────────────────────────────────────────

function FilterChip({
  title,
  options,
  selected,
  onChange,
}: {
  title: string
  options: { label: string; value: string }[]
  selected: string[]
  onChange: (values: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  const handleBlur = (e: React.FocusEvent<HTMLDivElement>) => {
    if (!ref.current?.contains(e.relatedTarget as Node)) {
      setOpen(false)
    }
  }

  const isActive = selected.length > 0

  const labelText = () => {
    if (!isActive) return null
    if (selected.length === 1) {
      return options.find(o => o.value === selected[0])?.label
    }
    return `${options.find(o => o.value === selected[0])?.label} +${selected.length - 1}`
  }

  function toggle(value: string) {
    if (selected.includes(value)) {
      onChange(selected.filter(v => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  return (
    <div ref={ref} className="relative" onBlur={handleBlur}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className={cx(
          'flex items-center gap-x-1.5 whitespace-nowrap rounded-md border px-2 py-1.5',
          'text-sm font-medium transition-colors',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500',
          isActive
            ? 'border-indigo-300 dark:border-indigo-700 bg-white dark:bg-gray-900'
            : 'border-dashed border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900',
          'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800',
        )}
      >
        {/* Plus/X icon */}
        <span
          onClick={(e) => {
            if (isActive) {
              e.stopPropagation()
              onChange([])
            }
          }}
        >
          <RiAddLine
            className={cx(
              '-ml-px size-4 shrink-0 transition-transform',
              isActive && 'rotate-45 hover:text-red-500',
            )}
            aria-hidden="true"
          />
        </span>

        <span className="text-xs">{title}</span>

        {isActive && (
          <>
            <span className="h-4 w-px bg-gray-300 dark:bg-gray-700" aria-hidden="true" />
            <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
              {labelText()}
            </span>
          </>
        )}

        <RiArrowDownSLine className="size-4 shrink-0 text-gray-500" aria-hidden="true" />
      </button>

      {open && (
        <div className={cx(
          'absolute left-0 top-full z-50 mt-1.5 min-w-48 rounded-lg border shadow-lg p-3',
          'bg-white dark:bg-gray-900',
          'border-gray-200 dark:border-gray-800',
        )}>
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2">
            Filter by {title}
          </p>
          <div className="space-y-2">
            {options.map(opt => (
              <label
                key={opt.value}
                className="flex items-center gap-2 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(opt.value)}
                  onChange={() => toggle(opt.value)}
                  className="rounded border-gray-300 dark:border-gray-600
                    text-indigo-600 focus:ring-indigo-500
                    bg-white dark:bg-gray-800"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
          {isActive && (
            <button
              onClick={() => { onChange([]); setOpen(false) }}
              className="mt-3 w-full text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors text-left"
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main filterbar ───────────────────────────────────────────────────────────

export function ControlsFilterbar({
  filters,
  onChange,
  globalFilter,
  onGlobalFilterChange,
}: ControlsFilterbarProps) {
  const isFiltered =
    filters.evidenceStatus.length > 0 ||
    filters.controlType.length > 0 ||
    globalFilter.length > 0

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">

      {/* Left: filter chips */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterChip
          title="Evidence Status"
          options={EVIDENCE_STATUS_OPTIONS}
          selected={filters.evidenceStatus}
          onChange={val => onChange({ ...filters, evidenceStatus: val })}
        />
        <FilterChip
          title="Control Type"
          options={CONTROL_TYPE_OPTIONS}
          selected={filters.controlType}
          onChange={val => onChange({ ...filters, controlType: val })}
        />
        {isFiltered && (
          <button
            onClick={() => {
              onChange({ evidenceStatus: [], controlType: [] })
              onGlobalFilterChange('')
            }}
            className="text-xs font-semibold text-indigo-600 dark:text-indigo-400
              hover:text-indigo-800 dark:hover:text-indigo-300 transition-colors px-1"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Right: search */}
      <Searchbar
        value={globalFilter}
        onChange={e => onGlobalFilterChange(e.target.value)}
        placeholder="Search controls…"
        className="w-48"
      />
    </div>
  )
}