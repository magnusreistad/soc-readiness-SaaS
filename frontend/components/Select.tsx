// Tremor Raw Select [v0.0.2]

"use client"

import * as SelectPrimitives from "@radix-ui/react-select"
import {
  RiArrowDownSLine,
  RiArrowUpSLine,
  RiCheckLine,
} from "@remixicon/react"
import * as React from "react"

import { cx, focusInput, hasErrorInput } from "@/lib/utils"

const Select = SelectPrimitives.Root
Select.displayName = "Select"

const SelectGroup = SelectPrimitives.Group
SelectGroup.displayName = "SelectGroup"

const SelectValue = SelectPrimitives.Value
SelectValue.displayName = "SelectValue"

const selectTriggerStyles = [
  cx(
    // base
    "group/trigger flex w-full select-none items-center justify-between gap-2 truncate rounded-md border px-2.5 py-1.5 shadow-sm outline-none transition sm:text-sm",
    // border color
    "border-gray-300 dark:border-gray-800",
    // text color
    "text-gray-900 dark:text-gray-50",
    // placeholder
    "data-[placeholder]:text-gray-400 data-[placeholder]:dark:text-gray-500",
    // background
    "bg-white dark:bg-gray-950",
    // hover
    "hover:bg-gray-50 dark:hover:bg-gray-950/50",
    // disabled
    "data-[disabled]:cursor-not-allowed",
    "data-[disabled]:border-gray-300 data-[disabled]:text-gray-400",
    "data-[disabled]:dark:border-gray-700 data-[disabled]:dark:text-gray-600",
    // focus
    focusInput,
  ),
]

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.Trigger> & {
    hasError?: boolean
  }
>(({ className, hasError, children, ...props }, forwardedRef) => (
  <SelectPrimitives.Trigger
    ref={forwardedRef}
    className={cx(
      selectTriggerStyles,
      hasError ? hasErrorInput : "",
      className,
    )}
    {...props}
  >
    <span className="flex-1 truncate text-left">{children}</span>
    <SelectPrimitives.Icon asChild>
      <RiArrowDownSLine
        className={cx(
          "size-4 shrink-0 text-gray-400 transition-transform duration-100",
          "group-data-[state=open]/trigger:-rotate-180",
          "dark:text-gray-600",
        )}
        aria-hidden="true"
      />
    </SelectPrimitives.Icon>
  </SelectPrimitives.Trigger>
))
SelectTrigger.displayName = "SelectTrigger"

const SelectScrollUpButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.ScrollUpButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.ScrollUpButton>
>(({ className, ...props }, forwardedRef) => (
  <SelectPrimitives.ScrollUpButton
    ref={forwardedRef}
    className={cx(
      "flex cursor-default items-center justify-center py-1",
      className,
    )}
    {...props}
  >
    <RiArrowUpSLine className="size-3.5 shrink-0 text-gray-400 dark:text-gray-600" />
  </SelectPrimitives.ScrollUpButton>
))
SelectScrollUpButton.displayName = "SelectScrollUpButton"

const SelectScrollDownButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.ScrollDownButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.ScrollDownButton>
>(({ className, ...props }, forwardedRef) => (
  <SelectPrimitives.ScrollDownButton
    ref={forwardedRef}
    className={cx(
      "flex cursor-default items-center justify-center py-1",
      className,
    )}
    {...props}
  >
    <RiArrowDownSLine className="size-3.5 shrink-0 text-gray-400 dark:text-gray-600" />
  </SelectPrimitives.ScrollDownButton>
))
SelectScrollDownButton.displayName = "SelectScrollDownButton"

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.Content>
>(({ className, children, position = "popper", ...props }, forwardedRef) => (
  <SelectPrimitives.Portal>
    <SelectPrimitives.Content
      ref={forwardedRef}
      className={cx(
        // base
        "relative z-50 overflow-hidden rounded-md border shadow-xl shadow-black/[2.5%]",
        // widths
        "min-w-[calc(var(--radix-select-trigger-width))] max-w-[calc(var(--radix-select-trigger-width))]",
        // border color
        "border-gray-200 dark:border-gray-800",
        // background
        "bg-white dark:bg-gray-950",
        // transition
        "data-[state=open]:animate-in data-[state=closed]:animate-out",
        "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
        "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
        "data-[side=bottom]:slide-in-from-top-2",
        "data-[side=left]:slide-in-from-right-2",
        "data-[side=right]:slide-in-from-left-2",
        "data-[side=top]:slide-in-from-bottom-2",
        position === "popper" &&
          "data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1",
        className,
      )}
      position={position}
      {...props}
    >
      <SelectScrollUpButton />
      <SelectPrimitives.Viewport
        className={cx(
          "p-1",
          position === "popper" &&
            "h-[var(--radix-select-trigger-height)] w-full min-w-[calc(var(--radix-select-trigger-width))]",
        )}
      >
        {children}
      </SelectPrimitives.Viewport>
      <SelectScrollDownButton />
    </SelectPrimitives.Content>
  </SelectPrimitives.Portal>
))
SelectContent.displayName = "SelectContent"

const SelectGroupLabel = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.Label>
>(({ className, ...props }, forwardedRef) => (
  <SelectPrimitives.Label
    ref={forwardedRef}
    className={cx(
      "px-3 py-1.5 text-xs font-semibold tracking-wide",
      "text-gray-500 dark:text-gray-500",
      className,
    )}
    {...props}
  />
))
SelectGroupLabel.displayName = "SelectGroupLabel"

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.Item>
>(({ className, children, ...props }, forwardedRef) => (
  <SelectPrimitives.Item
    ref={forwardedRef}
    className={cx(
      // base
      "relative flex w-full cursor-pointer select-none items-center rounded py-1.5 pl-3 pr-8 outline-none transition-colors sm:text-sm",
      // text color
      "text-gray-900 dark:text-gray-50",
      // hover
      "hover:bg-gray-100 dark:hover:bg-gray-800",
      // focus
      "focus-visible:bg-gray-100 dark:focus-visible:bg-gray-800",
      // disabled
      "data-[disabled]:pointer-events-none data-[disabled]:text-gray-400 dark:data-[disabled]:text-gray-600",
      className,
    )}
    {...props}
  >
    <SelectPrimitives.ItemText>{children}</SelectPrimitives.ItemText>
    <span className="absolute right-2 flex size-4 items-center justify-center">
      <SelectPrimitives.ItemIndicator>
        <RiCheckLine className="size-full shrink-0 text-indigo-600 dark:text-indigo-400" />
      </SelectPrimitives.ItemIndicator>
    </span>
  </SelectPrimitives.Item>
))
SelectItem.displayName = "SelectItem"

const SelectSeparator = React.forwardRef<
  React.ElementRef<typeof SelectPrimitives.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitives.Separator>
>(({ className, ...props }, forwardedRef) => (
  <SelectPrimitives.Separator
    ref={forwardedRef}
    className={cx(
      "-mx-1 my-1 h-px border-t border-gray-200 dark:border-gray-800",
      className,
    )}
    {...props}
  />
))
SelectSeparator.displayName = "SelectSeparator"

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectGroupLabel,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
}