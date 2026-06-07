import type { ReactNode } from 'react'

import { EmptyState } from './EmptyState'

type DisconnectedStateProps = {
  title?: string
  hint?: string
  actions?: ReactNode
  className?: string
}

export function DisconnectedState({
  title = 'Connection needed',
  hint = 'Connect the required source before this section can show current information.',
  actions,
  className = '',
}: DisconnectedStateProps) {
  return (
    <EmptyState
      title={title}
      hint={hint}
      actions={actions}
      className={className}
    />
  )
}
