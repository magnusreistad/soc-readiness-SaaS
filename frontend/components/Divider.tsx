// Tremor Raw Divider [v0.0.1]

import React from "react"
import { cx } from "@/lib/utils"

interface DividerProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string
}

const Divider = React.forwardRef<HTMLDivElement, DividerProps>(
  ({ className, label, ...props }, forwardedRef) => (
    <div
      ref={forwardedRef}
      className={cx(
        "mx-auto flex w-full items-center justify-between gap-3",
        className,
      )}
      {...props}
    >
      <div
        className={cx(
          "h-px w-full",
          "bg-gray-200 dark:bg-gray-800",
        )}
      />
      {label ? (
        <span
          className={cx(
            "text-sm whitespace-nowrap",
            "text-gray-500 dark:text-gray-500",
          )}
        >
          {label}
        </span>
      ) : null}
      {label ? (
        <div
          className={cx(
            "h-px w-full",
            "bg-gray-200 dark:bg-gray-800",
          )}
        />
      ) : null}
    </div>
  ),
)

Divider.displayName = "Divider"

export { Divider }