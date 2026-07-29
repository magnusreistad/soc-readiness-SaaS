// Tremor Raw Card [v0.0.1]

import React from "react"
import { cx } from "@/lib/utils"

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, forwardedRef) => (
    <div
      ref={forwardedRef}
      className={cx(
        // base
        "relative w-full rounded-lg border p-6 text-left shadow-sm",
        // border color
        "border-gray-200 dark:border-gray-800",
        // background
        "bg-white dark:bg-gray-950",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
)

Card.displayName = "Card"

export { Card }