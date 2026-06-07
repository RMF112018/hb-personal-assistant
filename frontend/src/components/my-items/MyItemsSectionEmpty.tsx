import { EmptyState } from '../common/EmptyState'
import { MyItemsSettingsLink } from './MyItemsActions'

type MyItemsSectionEmptyProps = {
  title: string
  hint?: string
  showSettingsAction?: boolean
}

export function MyItemsSectionEmpty({
  title,
  hint = 'Waiting for first update approval.',
  showSettingsAction = false,
}: MyItemsSectionEmptyProps) {
  return (
    <EmptyState
      title={title}
      hint={hint}
      actions={showSettingsAction ? <MyItemsSettingsLink /> : undefined}
    />
  )
}
