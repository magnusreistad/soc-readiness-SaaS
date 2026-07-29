// frontend/data/data.ts
// Shared reference data for Settings UI components.

export const roles = [
  { value: "admin",   label: "Admin"   },
  { value: "analyst", label: "Analyst" },
  { value: "auditor", label: "Auditor" },
] as const

export type RoleValue = (typeof roles)[number]["value"]