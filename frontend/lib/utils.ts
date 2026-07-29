import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

// Tremor cx utility — merges Tailwind classes safely
export function cx(...args: ClassValue[]) {
  return twMerge(clsx(...args))
}

// Formatters used by Tremor table components
export const formatters = {
  currency: (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value),

  number: (value: number) =>
    new Intl.NumberFormat("en-US").format(value),

  percentage: (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "percent",
      minimumFractionDigits: 1,
    }).format(value / 100),

  date: (value: string) =>
    new Date(value).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }),
}

export const focusRing = [
  "outline outline-offset-2 outline-0 focus-visible:outline-2",
  "outline-indigo-500 dark:outline-indigo-500",
].join(" ")

// Used by Searchbar and other input-style Tremor primitives
export const focusInput = [
  "focus:ring-2",
  "focus:ring-indigo-200 focus:dark:ring-indigo-700/30",
  "focus:border-indigo-500 focus:dark:border-indigo-700",
].join(" ")

// Applied when hasError={true} on input primitives
export const hasErrorInput = [
  "ring-2",
  "border-red-500 dark:border-red-700",
  "ring-red-200 dark:ring-red-700/30",
].join(" ")