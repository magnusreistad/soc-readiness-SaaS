'use client'

import { useState } from 'react'
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
import {
  CriteriaPicker,
  CONTROL_TYPE_OPTIONS,
  FREQUENCY_OPTIONS,
} from './ControlDrawer'

interface AddControlModalProps {
  open:         boolean
  onOpenChange: (open: boolean) => void
  orgScope:     string[]
  onCreated:    () => void
}

const EMPTY_FORM = {
  title:       '',
  description: '',
  controlType: 'manual',
  frequency:   '',
  criteria:    [] as string[],
}

export default function AddControlModal({ open, onOpenChange, orgScope, onCreated }: AddControlModalProps) {
  const [form,    setForm]    = useState(EMPTY_FORM)
  const [saving,  setSaving]  = useState(false)
  const [error,   setError]   = useState('')

  function reset() {
    setForm(EMPTY_FORM)
    setError('')
  }

  function close() {
    onOpenChange(false)
    // Wait out the dialog's close transition before clearing fields
    setTimeout(reset, 200)
  }

  async function handleCreate() {
    if (!form.title.trim()) {
      setError('Name is required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.post('controls', {
        title:        form.title.trim(),
        description:  form.description,
        control_type: form.controlType,
        frequency:    form.frequency || null,
        tsc_criteria: form.criteria,
      })
      onCreated()
      close()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create control. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={v => (v ? onOpenChange(v) : close())}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Add control</DialogTitle>
          <DialogDescription>
            Create a new control and map it to the TSC criteria it addresses. A control ID is
            assigned automatically based on its first mapped criterion.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-5">

          {/* Name — full width */}
          <div className="col-span-2">
            <Label htmlFor="add-title" className="font-medium">Name</Label>
            <Input
              id="add-title"
              type="text"
              placeholder="e.g. Quarterly access review"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="mt-2"
            />
          </div>

          {/* Control Type + Frequency side by side */}
          <div>
            <Label className="font-medium">Control Type</Label>
            <Select value={form.controlType} onValueChange={v => setForm(f => ({ ...f, controlType: v }))}>
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
            <Select
              value={form.frequency || 'none'}
              onValueChange={v => setForm(f => ({ ...f, frequency: v === 'none' ? '' : v }))}
            >
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
            <Label htmlFor="add-desc" className="font-medium">Description</Label>
            <textarea
              id="add-desc"
              rows={3}
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
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
              selected={form.criteria}
              onChange={criteria => setForm(f => ({ ...f, criteria }))}
              orgScope={orgScope}
            />
          </div>

          {error && (
            <p className="col-span-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10
              border border-red-200 dark:border-red-500/30 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <DialogFooter className="mt-6">
          <Button variant="secondary" onClick={close}>Cancel</Button>
          <Button variant="primary" onClick={handleCreate} isLoading={saving} loadingText="Creating…">
            Create control
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
