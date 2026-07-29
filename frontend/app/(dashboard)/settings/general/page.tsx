"use client"

import { useEffect, useState } from "react"
import { createClient } from "@/lib/supabase"
import { api } from "@/lib/api"
import { Button } from "@/components/Button"
import { Card } from "@/components/Card"
import { Checkbox } from "@/components/Checkbox"
import { Divider } from "@/components/Divider"
import { Label } from "@/components/Label"
import { RiLockLine } from "@remixicon/react"

// ── TSC category definitions ──────────────────────────────────────────────────

const TSC_CATEGORIES = [
  { key: "Security",             label: "Security",             desc: "CC1–CC9 — required for all SOC 2 examinations" },
  { key: "Availability",         label: "Availability",         desc: "A1 — system availability commitments" },
  { key: "Confidentiality",      label: "Confidentiality",      desc: "C1 — protection of confidential information" },
  { key: "Processing Integrity", label: "Processing Integrity", desc: "PI1 — complete, valid, and accurate processing" },
  { key: "Privacy",              label: "Privacy",              desc: "P1–P8 — personal information lifecycle" },
] as const

// ── JWT helper ────────────────────────────────────────────────────────────────

function getRoleFromToken(accessToken: string | undefined): string {
  if (!accessToken) return "analyst"
  try {
    return (JSON.parse(atob(accessToken.split(".")[1])).role as string) ?? "analyst"
  } catch {
    return "analyst"
  }
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function GeneralSettingsPage() {
  const [roleLoaded, setRoleLoaded] = useState(false)
  const [role,       setRole      ] = useState<string>("analyst")

  const [examType, setExamType] = useState<"type1" | "type2">("type2")
  const [tscScope, setTscScope] = useState<string[]>(["Security"])

  const [saving,   setSaving  ] = useState(false)
  const [feedback, setFeedback] = useState<{ msg: string; ok: boolean } | null>(null)

  useEffect(() => {
    const supabase = createClient()

    // Resolve role from JWT in parallel with loading org settings
    supabase.auth.getSession().then(({ data: { session } }) => {
      setRole(getRoleFromToken(session?.access_token))
      setRoleLoaded(true)
    })

    // Use public endpoint — any authenticated user can read current config
    api
      .get("org/settings")
      .then((data: { tsc_scope?: string[]; examination_type?: string }) => {
        setTscScope(data.tsc_scope ?? ["Security"])
        setExamType((data.examination_type as "type1" | "type2") ?? "type2")
      })
      .catch(() => {})
  }, [])

  function flash(msg: string, ok = true) {
    setFeedback({ msg, ok })
    setTimeout(() => setFeedback(null), 5000)
  }

  function toggleCategory(key: string) {
    if (key === "Security") return
    setTscScope((prev) =>
      prev.includes(key) ? prev.filter((c) => c !== key) : [...prev, key],
    )
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.patch("admin/org/examination-type", { examination_type: examType })
      await api.patch("admin/org/tsc-scope", { categories: tscScope })
      flash("Examination settings saved.")
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Save failed.", false)
    } finally {
      setSaving(false)
    }
  }

  const isAdmin = role === "admin"

  if (!roleLoaded) {
    return (
      <div className="py-12 text-center text-sm text-gray-400 dark:text-gray-600">
        Loading…
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <section aria-labelledby="exam-settings-heading">
        <div className="grid grid-cols-1 gap-x-14 gap-y-8 md:grid-cols-3">

          {/* ── Left: description ── */}
          <div>
            <h2
              id="exam-settings-heading"
              className="scroll-mt-10 font-semibold text-gray-900 dark:text-gray-50"
            >
              Examination Setup
            </h2>
            <p className="mt-1 text-sm leading-6 text-gray-500">
              Configure the examination type and Trust Service Criteria in scope.
              These settings drive the Controls inventory and readiness modules.
            </p>
          </div>

          {/* ── Right: form ── */}
          <div className="md:col-span-2">

            {/* Admin-only read-only notice */}
            {!isAdmin && (
              <div className="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-900 dark:bg-gray-900">
                <p className="flex items-center gap-2 text-sm text-gray-500">
                  <RiLockLine className="size-4 shrink-0" aria-hidden="true" />
                  Examination settings can only be changed by workspace administrators.
                  You are viewing the current configuration in read-only mode.
                </p>
              </div>
            )}

            {/* Feedback banner */}
            {feedback && (
              <div
                className={`mb-6 rounded-lg border px-4 py-3 text-sm ${
                  feedback.ok
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/50 dark:bg-emerald-950/30 dark:text-emerald-400"
                    : "border-red-200 bg-red-50 text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-400"
                }`}
              >
                {feedback.msg}
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-6">

              {/* Examination Type */}
              <div className="col-span-full">
                <Label className="font-medium">Examination Type</Label>
                <div className="mt-3 flex gap-3">
                  {(["type1", "type2"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => isAdmin && setExamType(t)}
                      disabled={!isAdmin}
                      aria-pressed={examType === t}
                      className={`flex-1 rounded-lg border px-4 py-3 text-left text-sm font-medium transition-colors disabled:cursor-not-allowed ${
                        examType === t
                          ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-500 dark:bg-indigo-950/40 dark:text-indigo-300"
                          : "border-gray-200 bg-white text-gray-600 hover:border-gray-300 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400 dark:hover:border-gray-700"
                      }`}
                    >
                      <p className="font-semibold">
                        {t === "type1" ? "Type 1" : "Type 2"}
                      </p>
                      <p className="mt-0.5 text-xs font-normal text-gray-500 dark:text-gray-500">
                        {t === "type1"
                          ? "Point-in-time — design only, no testing phase"
                          : "Period of time — design and operating effectiveness"}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* TSC Scope */}
              <div className="col-span-full">
                <Label className="font-medium">Trust Service Criteria in Scope</Label>
                <p className="mt-1 text-xs text-gray-500">
                  Security is required for all SOC 2 examinations and cannot be deselected.
                </p>
                <ul role="list" className="mt-3 divide-y divide-gray-200 dark:divide-gray-800">
                  {TSC_CATEGORIES.map((cat) => {
                    const checked = tscScope.includes(cat.key)
                    const locked  = cat.key === "Security" || !isAdmin
                    return (
                      <li key={cat.key} className="flex items-center gap-x-3 py-3">
                        <Checkbox
                          id={`tsc-${cat.key}`}
                          checked={checked}
                          disabled={locked}
                          onCheckedChange={() => toggleCategory(cat.key)}
                        />
                        <Label
                          htmlFor={`tsc-${cat.key}`}
                          disabled={locked}
                          className="cursor-pointer"
                        >
                          <span className="font-medium">{cat.label}</span>
                          <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
                            {cat.desc}
                          </span>
                        </Label>
                      </li>
                    )
                  })}
                </ul>
              </div>

              {/* Save */}
              {isAdmin && (
                <div className="col-span-full flex justify-end">
                  <Button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    isLoading={saving}
                    loadingText="Saving…"
                  >
                    Save settings
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <Divider />
    </div>
  )
}