// Tremor Raw TabNavigation [v0.0.1]

"use client"

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cx, focusRing } from "@/lib/utils"

// ── TabNavigation wrapper ──────────────────────────────────────────────────

const TabNavigation = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, forwardedRef) => (
  <div
    ref={forwardedRef}
    className={cx(
      "flex overflow-x-auto border-b",
      "border-gray-200 dark:border-gray-800",
      className,
    )}
    {...props}
  >
    {children}
  </div>
))
TabNavigation.displayName = "TabNavigation"

// ── TabNavigationLink ──────────────────────────────────────────────────────

interface TabNavigationLinkProps extends React.HTMLAttributes<HTMLElement> {
  active?: boolean
  disabled?: boolean
  asChild?: boolean
}

const TabNavigationLink = React.forwardRef<
  HTMLElement,
  TabNavigationLinkProps
>(
  (
    { active, disabled, className, asChild = false, children, ...props },
    forwardedRef,
  ) => {
    const Component = asChild ? Slot : "span"

    return (
      <Component
        ref={forwardedRef as React.Ref<HTMLSpanElement>}
        className={cx(
          // base
          "-mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-[3px] px-3 pb-3 text-sm font-medium transition-all",
          // active state
          active
            ? [
                "border-indigo-500 text-indigo-600",
                "dark:border-indigo-400 dark:text-indigo-400",
              ]
            : [
                "border-transparent text-gray-500",
                "hover:text-gray-700 hover:border-gray-300",
                "dark:text-gray-400 dark:hover:text-gray-300 dark:hover:border-gray-700",
              ],
          // disabled
          disabled &&
            "pointer-events-none opacity-50",
          // focus
          focusRing,
          className,
        )}
        {...props}
      >
        {children}
      </Component>
    )
  },
)
TabNavigationLink.displayName = "TabNavigationLink"

export { TabNavigation, TabNavigationLink }