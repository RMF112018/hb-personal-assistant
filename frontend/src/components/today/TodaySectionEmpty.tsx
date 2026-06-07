import type { ReactNode } from 'react'

import { EmptyState } from '../common/EmptyState'

type TodaySectionEmptyProps = {
  title?: string
  hint?: string
  actions?: ReactNode
}

export function TodaySectionEmpty({
  title = 'No items need attention right now.',
  hint,
  actions,
}: TodaySectionEmptyProps) {
  return <EmptyState title={title} hint={hint} actions={actions} />
}
