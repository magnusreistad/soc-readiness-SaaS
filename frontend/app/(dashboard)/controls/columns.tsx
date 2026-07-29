"use client"

import { Badge } from "@/components/Badge"
import { ColumnDef, createColumnHelper } from "@tanstack/react-table"
import { DataTableColumnHeader } from "./DataTableColumnHeader"
import {
  Control,
  EVIDENCE_STATUS_CONFIG,
  EvidenceStatus,
  PhaseTab,
  getPhaseStatus,
} from "./page"

const columnHelper = createColumnHelper<Control>()

const EVIDENCE_BADGE_VARIANT: Record<EvidenceStatus, "neutral" | "warning" | "success" | "error" | "default"> = {
  not_started:  "neutral",
  pending:      "default",
  sufficient:   "success",
  improvements: "warning",
}

const CONTROL_TYPE_LABELS: Record<string, string> = {
  automated:           "Auto",
  manual:              "Manual",
  it_dependent_manual: "ITDM",
  itdm:                "ITDM",
}

export function createColumns(
  activeTab: PhaseTab,
  onOpenDrawer: (control: Control) => void,
): ColumnDef<Control>[] {
  return [
    // ── Control ID ────────────────────────────────────────────────────────────
    columnHelper.accessor("control_id", {
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Control ID" />
      ),
      enableSorting: true,
      enableHiding: false,
      meta: {
        displayName: "Control ID",
        className: "text-left",
      },
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold whitespace-nowrap
            text-indigo-600 dark:text-indigo-400
            bg-indigo-50 dark:bg-indigo-500/10
            border border-indigo-100 dark:border-indigo-500/30
            px-2 py-0.5 rounded">
            {row.original.control_id}
          </span>
          {row.original.control_type && (
            <span className="text-[10px] font-medium whitespace-nowrap hidden lg:inline
              text-gray-500 dark:text-gray-400
              bg-gray-100 dark:bg-gray-700
              px-1.5 py-0.5 rounded">
              {CONTROL_TYPE_LABELS[row.original.control_type] ?? row.original.control_type}
            </span>
          )}
        </div>
      ),
    }) as ColumnDef<Control>,

    // ── Title ─────────────────────────────────────────────────────────────────
    columnHelper.accessor("title", {
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Title" />
      ),
      enableSorting: true,
      meta: {
        displayName: "Title",
        className: "text-left",
      },
      cell: ({ row }) => (
        <div className="min-w-0">
          <p className="text-sm font-medium truncate
            text-gray-900 dark:text-gray-100">
            {row.original.title}
          </p>
          {activeTab === "all" && row.original.next_action && (
            <p className="text-xs truncate mt-0.5
              text-gray-400 dark:text-gray-500">
              {row.original.next_action}
            </p>
          )}
          {activeTab !== "all" && row.original.tsc_criteria?.[0] && (
            <p className="text-xs mt-0.5
              text-gray-400 dark:text-gray-500">
              {row.original.tsc_criteria[0]}
            </p>
          )}
        </div>
      ),
    }) as ColumnDef<Control>,

    // ── Evidence Status ───────────────────────────────────────────────────────
    columnHelper.display({
      id: "evidence_status",
      header: ({ column }) => (
        <DataTableColumnHeader
          column={column}
          title={
            activeTab === "all"
              ? "Evidence Status"
              : `${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Status`
          }
        />
      ),
      enableSorting: false,
      meta: {
        displayName: "Evidence Status",
        className: "text-left",
      },
      cell: ({ row }) => {
        const status  = getPhaseStatus(row.original, activeTab)
        const variant = EVIDENCE_BADGE_VARIANT[status]
        const cfg     = EVIDENCE_STATUS_CONFIG[status]
        return <Badge variant={variant}>{cfg.label}</Badge>
      },
    }) as ColumnDef<Control>,

    // ── Last Upload ───────────────────────────────────────────────────────────
    columnHelper.accessor("last_evidence_at", {
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Last Upload" />
      ),
      enableSorting: true,
      meta: {
        displayName: "Last Upload",
        className: "text-left tabular-nums",
      },
      cell: ({ getValue }) => {
        const val = getValue()
        return (
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {val
              ? new Date(val).toLocaleDateString("en-US", {
                  month: "short",
                  day:   "numeric",
                  year:  "numeric",
                })
              : "—"}
          </span>
        )
      },
    }) as ColumnDef<Control>,

    // ── Owner ─────────────────────────────────────────────────────────────────
    columnHelper.accessor("owner", {
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Owner" />
      ),
      enableSorting: true,
      meta: {
        displayName: "Owner",
        className: "text-left",
      },
      cell: ({ getValue }) => {
        const owner = getValue()
        if (!owner) return <span className="text-sm text-gray-300 dark:text-gray-600">—</span>
        return (
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 uppercase
              bg-indigo-100 dark:bg-indigo-500/20
              text-indigo-700 dark:text-indigo-400
              text-[10px] font-bold">
              {owner.charAt(0)}
            </div>
            <span className="text-sm truncate hidden xl:block
              text-gray-600 dark:text-gray-300">
              {owner}
            </span>
          </div>
        )
      },
    }) as ColumnDef<Control>,

    // ── Row action ────────────────────────────────────────────────────────────
    columnHelper.display({
      id: "open",
      header: "",
      enableSorting: false,
      enableHiding: false,
      meta: {
        displayName: "Open",
        className: "text-right",
      },
      cell: ({ row }) => (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onOpenDrawer(row.original)
          }}
          className="text-xs font-medium whitespace-nowrap transition-colors
            text-indigo-600 hover:text-indigo-800
            dark:text-indigo-400 dark:hover:text-indigo-300"
        >
          Open →
        </button>
      ),
    }) as ColumnDef<Control>,
  ]
}