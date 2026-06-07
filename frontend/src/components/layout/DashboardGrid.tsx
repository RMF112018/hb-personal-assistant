import type { ReactNode } from 'react'

type DashboardGridProps = {
  children: ReactNode
  columns?: 'cards' | 'sections' | 'metrics'
  gap?: 'sm' | 'md' | 'lg'
  className?: string
}

const columnClasses: Record<NonNullable<DashboardGridProps['columns']>, string> = {
  cards: 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3',
  sections: 'grid-cols-1 lg:grid-cols-2',
  metrics: 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-4',
}

const gapClasses: Record<NonNullable<DashboardGridProps['gap']>, string> = {
  sm: 'gap-2',
  md: 'gap-3',
  lg: 'gap-4',
}

export function DashboardGrid({
  children,
  columns = 'cards',
  gap = 'md',
  className = '',
}: DashboardGridProps) {
  return (
    <div className={`grid ${columnClasses[columns]} ${gapClasses[gap]} ${className}`}>
      {children}
    </div>
  )
}
