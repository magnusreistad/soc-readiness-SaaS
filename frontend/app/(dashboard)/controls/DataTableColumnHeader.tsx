import { RiArrowDownSLine, RiArrowUpSLine } from "@remixicon/react"
import { Column } from "@tanstack/react-table"
import { cx } from "@/lib/utils"

interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>
  title: string
}

export function DataTableColumnHeader<TData, TValue>({
  column,
  title,
  className,
}: DataTableColumnHeaderProps<TData, TValue>) {
  if (!column.getCanSort()) {
    return (
      <div className={cx("text-gray-700 dark:text-gray-300", className)}>
        {title}
      </div>
    )
  }

  return (
    <div
      onClick={column.getToggleSortingHandler()}
      className={cx(
        "inline-flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1",
        "text-gray-700 dark:text-gray-300",
        "hover:bg-gray-100 dark:hover:bg-gray-800",
        "-mx-2",
        className,
      )}
    >
      <span>{title}</span>
      <div className="-space-y-2">
        <RiArrowUpSLine
          className={cx(
            "size-3.5 text-gray-700 dark:text-gray-300",
            column.getIsSorted() === "desc" ? "opacity-30" : "",
          )}
          aria-hidden="true"
        />
        <RiArrowDownSLine
          className={cx(
            "size-3.5 text-gray-700 dark:text-gray-300",
            column.getIsSorted() === "asc" ? "opacity-30" : "",
          )}
          aria-hidden="true"
        />
      </div>
    </div>
  )
}