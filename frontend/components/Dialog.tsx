// Tremor Raw Dialog [v0.0.2]

"use client"

import * as DialogPrimitives from "@radix-ui/react-dialog"
import { RiCloseLine } from "@remixicon/react"
import * as React from "react"

import { cx, focusRing } from "@/lib/utils"

const Dialog = DialogPrimitives.Root
Dialog.displayName = "Dialog"

const DialogTrigger = DialogPrimitives.Trigger
DialogTrigger.displayName = "DialogTrigger"

const DialogClose = DialogPrimitives.Close
DialogClose.displayName = "DialogClose"

const DialogPortal = DialogPrimitives.Portal
DialogPortal.displayName = "DialogPortal"

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitives.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitives.Overlay>
>(({ className, ...props }, forwardedRef) => (
  <DialogPrimitives.Overlay
    ref={forwardedRef}
    className={cx(
      "fixed inset-0 z-50 overflow-y-auto",
      // background
      "bg-black/40 dark:bg-black/60",
      // animation
      "data-[state=open]:animate-in data-[state=closed]:animate-out",
      "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
))
DialogOverlay.displayName = "DialogOverlay"

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitives.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitives.Content>
>(({ className, children, ...props }, forwardedRef) => (
  <DialogPortal>
    <DialogOverlay>
      <div className="flex min-h-full items-center justify-center p-4">
        <DialogPrimitives.Content
          ref={forwardedRef}
          className={cx(
            // base
            "relative w-full max-w-lg rounded-xl p-6 shadow-xl",
            // background
            "bg-white dark:bg-gray-950",
            // border
            "border border-gray-200 dark:border-gray-800",
            // animation
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
            "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
            className,
          )}
          {...props}
        >
          {children}
          <DialogPrimitives.Close
            className={cx(
              "absolute right-4 top-4 rounded-md p-1",
              "text-gray-400 hover:text-gray-600 dark:text-gray-600 dark:hover:text-gray-400",
              "transition-colors",
              focusRing,
            )}
            aria-label="Close"
          >
            <RiCloseLine className="size-4 shrink-0" aria-hidden="true" />
          </DialogPrimitives.Close>
        </DialogPrimitives.Content>
      </div>
    </DialogOverlay>
  </DialogPortal>
))
DialogContent.displayName = "DialogContent"

const DialogHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, forwardedRef) => (
  <div
    ref={forwardedRef}
    className={cx("flex flex-col gap-1 pr-8", className)}
    {...props}
  />
))
DialogHeader.displayName = "DialogHeader"

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitives.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitives.Title>
>(({ className, ...props }, forwardedRef) => (
  <DialogPrimitives.Title
    ref={forwardedRef}
    className={cx(
      "text-base font-semibold",
      "text-gray-900 dark:text-gray-50",
      className,
    )}
    {...props}
  />
))
DialogTitle.displayName = "DialogTitle"

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitives.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitives.Description>
>(({ className, ...props }, forwardedRef) => (
  <DialogPrimitives.Description
    ref={forwardedRef}
    className={cx("text-sm text-gray-500 dark:text-gray-400", className)}
    {...props}
  />
))
DialogDescription.displayName = "DialogDescription"

const DialogFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, forwardedRef) => (
  <div
    ref={forwardedRef}
    className={cx(
      "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
      className,
    )}
    {...props}
  />
))
DialogFooter.displayName = "DialogFooter"

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
}