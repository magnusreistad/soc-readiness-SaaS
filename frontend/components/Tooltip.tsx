// Tremor Raw Tooltip [v0.0.2]

"use client"

import * as TooltipPrimitives from "@radix-ui/react-tooltip"
import * as React from "react"

import { cx } from "@/lib/utils"

const TooltipProvider = TooltipPrimitives.Provider
TooltipProvider.displayName = "TooltipProvider"

const TooltipTrigger = TooltipPrimitives.Trigger
TooltipTrigger.displayName = "TooltipTrigger"

interface TooltipProps
  extends Omit<TooltipPrimitives.TooltipContentProps, "content">,
    Pick<
      TooltipPrimitives.TooltipProps,
      "open" | "defaultOpen" | "onOpenChange" | "delayDuration"
    > {
  content: React.ReactNode
  triggerAsChild?: boolean
}

const Tooltip = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitives.Content>,
  TooltipProps
>(
  (
    {
      children,
      className,
      content,
      delayDuration,
      defaultOpen,
      open,
      side = "top",
      sideOffset = 4,
      onOpenChange,
      triggerAsChild = false,
      ...props
    }: TooltipProps,
    forwardedRef,
  ) => (
    <TooltipPrimitives.Provider delayDuration={150}>
      <TooltipPrimitives.Root
        open={open}
        defaultOpen={defaultOpen}
        onOpenChange={onOpenChange}
        delayDuration={delayDuration}
        tremor-id="tremor-raw"
      >
        <TooltipPrimitives.Trigger asChild={triggerAsChild}>
          {children}
        </TooltipPrimitives.Trigger>
        <TooltipPrimitives.Portal>
          <TooltipPrimitives.Content
            ref={forwardedRef}
            side={side}
            sideOffset={sideOffset}
            className={cx(
              // base
              "z-50 max-w-60 rounded-md px-2.5 py-1.5 text-center text-xs leading-normal shadow-md",
              // text color
              "text-gray-50 dark:text-gray-900",
              // background
              "bg-gray-900 dark:bg-gray-50",
              // animation
              "data-[state=delayed-open]:data-[side=bottom]:animate-in",
              "data-[state=delayed-open]:data-[side=top]:animate-in",
              "data-[state=delayed-open]:data-[side=left]:animate-in",
              "data-[state=delayed-open]:data-[side=right]:animate-in",
              "data-[state=delayed-open]:data-[side=bottom]:fade-in-0",
              "data-[state=delayed-open]:data-[side=bottom]:slide-in-from-top-1",
              "data-[state=delayed-open]:data-[side=top]:fade-in-0",
              "data-[state=delayed-open]:data-[side=top]:slide-in-from-bottom-1",
              className,
            )}
            {...props}
          >
            {content}
          </TooltipPrimitives.Content>
        </TooltipPrimitives.Portal>
      </TooltipPrimitives.Root>
    </TooltipPrimitives.Provider>
  ),
)

Tooltip.displayName = "Tooltip"

export { Tooltip, TooltipProvider, TooltipTrigger }