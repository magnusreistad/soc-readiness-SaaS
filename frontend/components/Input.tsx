// Tremor Raw Input [v0.0.2]

import * as React from "react"
import { tv, type VariantProps } from "tailwind-variants"

import { cx, focusInput, hasErrorInput } from "@/lib/utils"

const inputStyles = tv({
  base: [
    // base
    "relative block w-full appearance-none rounded-md border px-2.5 py-1.5 outline-none transition sm:text-sm",
    // border color
    "border-gray-300 dark:border-gray-800",
    // text color
    "text-gray-900 dark:text-gray-50",
    // placeholder color
    "placeholder-gray-400 dark:placeholder-gray-500",
    // background color
    "bg-white dark:bg-gray-950",
    // disabled
    "disabled:border-gray-300 disabled:bg-gray-100 disabled:text-gray-400",
    "disabled:dark:border-gray-700 disabled:dark:bg-gray-800 disabled:dark:text-gray-500",
    // focus
    focusInput,
    // invalid
    // "aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-red-200 aria-[invalid=true]:border-red-500"
  ],
  variants: {
    hasError: {
      true: hasErrorInput,
    },
    enableStepper: {
      false:
        "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
    },
  },
})

interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement>,
    VariantProps<typeof inputStyles> {
  inputClassName?: string
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      inputClassName,
      hasError,
      enableStepper,
      ...props
    }: InputProps,
    forwardedRef,
  ) => {
    return (
      <div className={cx("relative w-full", className)}>
        <input
          ref={forwardedRef}
          className={cx(inputStyles({ hasError, enableStepper }), inputClassName)}
          {...props}
        />
      </div>
    )
  },
)

Input.displayName = "Input"

export { Input, inputStyles }