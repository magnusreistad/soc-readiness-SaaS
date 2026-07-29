import { redirect } from "next/navigation"

/**
 * /settings → /settings/general
 *
 * The real content lives in the sub-routes:
 *   /settings/general  — Examination Setup (admin-gated edits)
 *   /settings/users    — User management
 */
export default function SettingsRootPage() {
  redirect("/settings/general")
}