import { Button } from "@/components/Button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/Dialog"
import { Input } from "@/components/Input"
import { Label } from "@/components/Label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/Select"
import { roles } from "@/data/data"
import { api } from "@/lib/api"
import { useState } from "react"

export type ModalAddUserProps = {
  children: React.ReactNode
  onSuccess?: (tempPassword: string, name: string, email: string) => void
}

export function ModalAddUser({ children, onSuccess }: ModalAddUserProps) {
  const [open,     setOpen    ] = useState(false)
  const [name,     setName    ] = useState("")
  const [email,    setEmail   ] = useState("")
  const [role,     setRole    ] = useState("analyst")
  const [inviting, setInviting] = useState(false)
  const [error,    setError   ] = useState<string | null>(null)

  function reset() {
    setName(""); setEmail(""); setRole("analyst"); setError(null)
  }

  async function handleSubmit() {
    setError(null)
    if (!name.trim() || !email.trim()) {
      setError("Name and email are required.")
      return
    }
    setInviting(true)
    try {
      const result = await api.post("admin/users/invite", { name, email, role })
      reset()
      setOpen(false)
      onSuccess?.(result.temp_password, name.trim(), email.trim())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invite failed.")
    } finally {
      setInviting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) reset()
      }}
    >
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Invite people to your workspace</DialogTitle>
          <DialogDescription>
            A temporary password will be generated and shown once. Share it with the
            user via a secure channel.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          {/* Name */}
          <div>
            <Label htmlFor="invite-name" className="font-medium">
              Full name
            </Label>
            <Input
              id="invite-name"
              type="text"
              placeholder="Alex Johnson"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-2"
            />
          </div>

          {/* Email */}
          <div>
            <Label htmlFor="invite-email" className="font-medium">
              Work email
            </Label>
            <Input
              id="invite-email"
              type="email"
              placeholder="alex@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-2"
            />
          </div>

          {/* Role */}
          <div>
            <Label htmlFor="invite-role" className="font-medium">
              Role
            </Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger id="invite-role" className="mt-2">
                <SelectValue placeholder="Select role…" />
              </SelectTrigger>
              <SelectContent>
                {roles.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-1.5 text-xs text-gray-500">
              {role === "analyst"
                ? "Read/write on incidents, controls, and evidence."
                : role === "auditor"
                ? "Read-only across all modules."
                : "Full access including user management and org settings."}
            </p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-400">
            {error}
          </p>
        )}

        <DialogFooter className="mt-6">
          <DialogClose asChild>
            <Button variant="secondary" className="w-full sm:w-fit">
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="button"
            className="w-full sm:w-fit"
            onClick={handleSubmit}
            isLoading={inviting}
            loadingText="Adding…"
          >
            Add user
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}