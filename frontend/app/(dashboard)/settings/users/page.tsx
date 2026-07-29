"use client"

import { useEffect, useState } from "react"
import { createClient } from "@/lib/supabase"
import { api } from "@/lib/api"
import { Button } from "@/components/Button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/Dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/Dropdown"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/Select"
import { Tooltip } from "@/components/Tooltip"
import { ModalAddUser } from "@/components/ui/settings/ModalAddUser"
import { roles } from "@/data/data"
import { RiAddLine, RiMore2Fill } from "@remixicon/react"

// ── Types ──────────────────────────────────────────────────────────────────────

type User = {
  id:         string
  name:       string
  email:      string
  role:       string
  is_active:  boolean
  created_at: string
  last_login: string | null
}

// ── JWT helper ────────────────────────────────────────────────────────────────

function getRoleFromToken(accessToken: string | undefined): string {
  if (!accessToken) return "analyst"
  try {
    return (JSON.parse(atob(accessToken.split(".")[1])).role as string) ?? "analyst"
  } catch {
    return "analyst"
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function initials(name: string, email: string): string {
  const n = name?.trim()
  if (n) {
    const parts = n.split(" ").filter(Boolean)
    return parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : n.slice(0, 2).toUpperCase()
  }
  return email.slice(0, 2).toUpperCase()
}

// ── Temp-password modal ────────────────────────────────────────────────────────

function TempPasswordModal({
  data,
  onClose,
}: {
  data: { password: string; name: string; email: string } | null
  onClose: () => void
}) {
  const [copied, setCopied] = useState(false)

  function copy() {
    if (!data) return
    navigator.clipboard.writeText(data.password).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <Dialog open={!!data} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-950/60">
              <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <div>
              <DialogTitle>User added</DialogTitle>
              {data && (
                <DialogDescription>{data.name} ({data.email})</DialogDescription>
              )}
            </div>
          </div>
        </DialogHeader>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
          Share the temporary password below with the user via a{" "}
          <span className="font-medium text-gray-900 dark:text-gray-200">secure channel</span>.
          It will not be shown again.
        </p>
        {data && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 dark:border-gray-800 dark:bg-gray-900">
            <code className="flex-1 select-all font-mono text-sm tracking-wide text-gray-900 dark:text-gray-100">
              {data.password}
            </code>
            <Button variant="ghost" className="shrink-0 text-xs text-indigo-600 dark:text-indigo-400" onClick={copy}>
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
        )}
        <DialogFooter className="mt-6">
          <DialogClose asChild>
            <Button className="w-full sm:w-fit">Done</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Delete confirmation dialog ─────────────────────────────────────────────────

function DeleteConfirmDialog({
  user,
  onConfirm,
  onCancel,
  isDeleting,
}: {
  user:       User | null
  onConfirm:  () => void
  onCancel:   () => void
  isDeleting: boolean
}) {
  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete user</DialogTitle>
          <DialogDescription>
            This will permanently remove{" "}
            <span className="font-medium text-gray-900 dark:text-gray-50">
              {user?.name || user?.email}
            </span>{" "}
            from the workspace and revoke all access immediately. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-6">
          <DialogClose asChild>
            <Button variant="secondary" className="w-full sm:w-fit">Cancel</Button>
          </DialogClose>
          <Button
            className="w-full bg-red-600 hover:bg-red-700 sm:w-fit"
            onClick={onConfirm}
            isLoading={isDeleting}
            loadingText="Deleting…"
          >
            Delete user
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Role selector cell ─────────────────────────────────────────────────────────

function RoleSelector({
  user,
  isCurrentUserAdmin,
  isChanging,
  adminCount,
  onRoleChange,
}: {
  user:               User
  isCurrentUserAdmin: boolean
  isChanging:         boolean
  adminCount:         number
  onRoleChange:       (userId: string, newRole: string) => void
}) {
  const selectEl = (disabled: boolean) => (
    <Select
      defaultValue={user.role}
      disabled={disabled || isChanging}
      onValueChange={(newRole) => onRoleChange(user.id, newRole)}
    >
      <SelectTrigger className="h-8 w-32">
        <SelectValue placeholder="Select" />
      </SelectTrigger>
      <SelectContent align="end">
        {roles.map((r) => (
          <SelectItem key={r.value} value={r.value}>
            {r.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )

  // Non-admin viewer: all rows locked
  if (!isCurrentUserAdmin) {
    return (
      <Tooltip content="Roles can only be changed by system admin." className="max-w-52 text-xs" sideOffset={5} triggerAsChild>
        <div>{selectEl(true)}</div>
      </Tooltip>
    )
  }

  // Admin viewer, but this row is the last admin: prevent demoting
  if (user.role === "admin" && adminCount <= 1) {
    return (
      <Tooltip content="A workspace must have at least one admin." className="max-w-44 text-xs" sideOffset={5} triggerAsChild>
        <div>{selectEl(true)}</div>
      </Tooltip>
    )
  }

  return selectEl(false)
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function UsersSettingsPage() {
  const [currentUserRole, setCurrentUserRole] = useState<string>("analyst")
  const [users,           setUsers          ] = useState<User[]>([])
  const [loading,         setLoading        ] = useState(true)
  const [error,           setError          ] = useState<string | null>(null)
  const [feedback,        setFeedback       ] = useState<{ msg: string; ok: boolean } | null>(null)
  const [tempPass,        setTempPass       ] = useState<{ password: string; name: string; email: string } | null>(null)
  const [changingRole,    setChangingRole   ] = useState<string | null>(null)
  const [userToDelete,    setUserToDelete   ] = useState<User | null>(null)
  const [isDeleting,      setIsDeleting     ] = useState(false)

  const isAdmin = currentUserRole === "admin"

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getSession().then(({ data: { session } }) => {
      setCurrentUserRole(getRoleFromToken(session?.access_token))
    })
    loadUsers()
  }, [])

  function loadUsers() {
    setLoading(true)
    // Use the public endpoint — accessible to all roles.
    // Admins can also hit /admin/users but /org/users is sufficient for display.
    api
      .get("org/users")
      .then((data: User[] | { items: User[] }) =>
        setUsers(Array.isArray(data) ? data : (data as { items: User[] }).items ?? []),
      )
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  function flash(msg: string, ok = true) {
    setFeedback({ msg, ok })
    setTimeout(() => setFeedback(null), 5000)
  }

  async function handleRoleChange(userId: string, newRole: string) {
    setChangingRole(userId)
    try {
      const updated: User = await api.patch(`admin/users/${userId}/role`, { role: newRole })
      setUsers((u) => u.map((x) => (x.id === updated.id ? updated : x)))
      flash("Role updated.")
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Role change failed.", false)
    } finally {
      setChangingRole(null)
    }
  }

  async function handleDeleteConfirmed() {
    if (!userToDelete) return
    setIsDeleting(true)
    try {
      await api.delete(`admin/users/${userToDelete.id}`)
      setUsers((u) => u.filter((x) => x.id !== userToDelete.id))
      flash(`${userToDelete.name || userToDelete.email} has been removed.`)
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Delete failed.", false)
    } finally {
      setIsDeleting(false)
      setUserToDelete(null)
    }
  }

  async function handleResetPassword(user: User) {
    if (!confirm(`Reset password for ${user.name || user.email}? A new temporary password will be generated.`)) return
    try {
      const result = await api.post(`admin/users/${user.id}/reset-password`, {})
      setTempPass({ password: result.temp_password, name: user.name, email: user.email })
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Reset failed.", false)
    }
  }

  return (
    <>
      <TempPasswordModal data={tempPass} onClose={() => setTempPass(null)} />
      <DeleteConfirmDialog
        user={userToDelete}
        onConfirm={handleDeleteConfirmed}
        onCancel={() => setUserToDelete(null)}
        isDeleting={isDeleting}
      />

      <section aria-labelledby="existing-users-heading">
        <div className="sm:flex sm:items-center sm:justify-between">
          <div>
            <h2
              id="existing-users-heading"
              className="scroll-mt-10 font-semibold text-gray-900 dark:text-gray-50"
            >
              Users
            </h2>
            <p className="text-sm leading-6 text-gray-500">
              {isAdmin
                ? "Workspace administrators can add, manage, and remove users."
                : "Contact a workspace administrator to make changes."}
            </p>
          </div>

          {/* Only admins see the Add user button */}
          {isAdmin && (
            <ModalAddUser
              onSuccess={(password, name, email) => {
                loadUsers()
                setTempPass({ password, name, email })
              }}
            >
              <Button className="mt-4 w-full gap-2 sm:mt-0 sm:w-fit">
                <RiAddLine className="-ml-1 size-4 shrink-0" aria-hidden="true" />
                Add user
              </Button>
            </ModalAddUser>
          )}
        </div>

        {feedback && (
          <div
            className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
              feedback.ok
                ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/50 dark:bg-emerald-950/30 dark:text-emerald-400"
                : "border-red-200 bg-red-50 text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-400"
            }`}
          >
            {feedback.msg}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-400">
            {error}
          </div>
        )}

        {loading ? (
          <div className="mt-8 text-center text-sm text-gray-400">Loading…</div>
        ) : (
          <ul role="list" className="mt-6 divide-y divide-gray-200 dark:divide-gray-800">
            {users.map((user) => (
              <li
                key={user.id}
                className="flex items-center justify-between gap-x-6 py-2.5"
              >
                {/* Avatar + name/email */}
                <div className="flex min-w-0 items-center gap-x-4 truncate">
                  <span
                    className="hidden size-9 shrink-0 items-center justify-center rounded-full border border-gray-300 bg-white text-xs font-medium text-gray-700 sm:flex dark:border-gray-700 dark:bg-gray-950 dark:text-gray-300"
                    aria-hidden="true"
                  >
                    {initials(user.name, user.email)}
                  </span>
                  <div className="min-w-0 truncate">
                    <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-50">
                      {user.name || "—"}
                    </p>
                    <p className="truncate text-xs text-gray-500">{user.email}</p>
                  </div>
                </div>

                {/* Role selector + kebab (kebab hidden for non-admins) */}
                <div className="flex items-center gap-2">
                  <RoleSelector
                    user={user}
                    isCurrentUserAdmin={isAdmin}
                    isChanging={changingRole === user.id}
                    adminCount={users.filter(u => u.role === "admin").length}
                    onRoleChange={handleRoleChange}
                  />

                  {isAdmin && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          className="group size-8 p-0 hover:border hover:border-gray-300 hover:bg-gray-50 data-[state=open]:border-gray-300 data-[state=open]:bg-gray-50 dark:hover:border-gray-700 dark:hover:bg-gray-900 dark:data-[state=open]:border-gray-700 dark:data-[state=open]:bg-gray-900"
                          aria-label="User actions"
                        >
                          <RiMore2Fill
                            className="size-4 shrink-0 text-gray-500 group-hover:text-gray-700 dark:text-gray-500 dark:group-hover:text-gray-400"
                            aria-hidden="true"
                          />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40">
                        <DropdownMenuItem onClick={() => handleResetPassword(user)}>
                          Reset password
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          disabled={user.role === "admin"}
                          className="text-red-600 dark:text-red-500"
                          onClick={() => setUserToDelete(user)}
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}