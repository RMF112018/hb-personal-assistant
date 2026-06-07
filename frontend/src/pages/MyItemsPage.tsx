/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query'

import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { DashboardCard } from '../components/layout/DashboardCard'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { MyItemsProjectsLink, MyItemsSettingsLink } from '../components/my-items/MyItemsActions'
import { MyItemsSectionEmpty } from '../components/my-items/MyItemsSectionEmpty'
import { MyItemsStatusRow } from '../components/my-items/MyItemsStatusRow'
import { MyWorkQueueItem } from '../components/my-items/MyWorkQueueItem'
import { api } from '../lib/api'

interface MyAttentionItem {
  kind?: string
  title?: string
  subject?: string
  name?: string
  note?: string
  project?: string
  source?: string
  age?: string
  when?: string
  count?: number
}

interface MyItemsEnvelope {
  surface?: string
  metric_cards?: any[]
  attention_items?: MyAttentionItem[]
  my_action_items?: MyAttentionItem[]
  my_meetings?: MyAttentionItem[]
  my_correspondence?: MyAttentionItem[]
  my_files?: MyAttentionItem[]
  my_followed_projects?: MyAttentionItem[]
  sections?: string[]
  freshness?: { overall?: string; minutes_ago_max?: number }
  confidence_summary?: { overall?: string }
  project_keys?: string[]
  empty_stale_error?: string | null
}

export function MyItemsPage() {
  const { data: my, isLoading, error } = useQuery({ queryKey: ['my-items'], queryFn: api.getMyItems })

  if (isLoading) {
    return <LoadingState label="Loading My Dashboard" />
  }

  if (error) {
    return (
      <ErrorState
        userMessage="We could not load your work queue."
        error={error}
        actions={<MyItemsSettingsLink />}
      />
    )
  }

  const myData: MyItemsEnvelope = (my as MyItemsEnvelope) || {}
  const sections = deriveSections(myData)
  const itemCount =
    sections.actions.length +
    sections.meetings.length +
    sections.correspondence.length +
    sections.files.length +
    sections.followed.length

  return (
    <PrimaryPageLayout
      status={
        <MyItemsStatusRow
          freshness={myData.freshness}
          confidence={myData.confidence_summary}
          itemCount={itemCount}
        />
      }
    >
      <DashboardGrid>
        <DashboardCard title="My Action Items" span="wide" tone="attention">
          <QueueList
            items={sections.actions}
            emptyTitle="No action items need your attention."
            emptyHint="Connect Microsoft 365 and Procore in Settings to populate this list."
            showSettingsAction
          />
        </DashboardCard>

        <DashboardCard title="My Meetings">
          <QueueList
            items={sections.meetings}
            emptyTitle="No meetings need your attention."
          />
        </DashboardCard>

        <DashboardCard title="My Correspondence">
          <QueueList
            items={sections.correspondence}
            emptyTitle="No correspondence needs your review."
          />
        </DashboardCard>

        <DashboardCard title="My Files">
          <QueueList
            items={sections.files}
            emptyTitle="No files need your review."
          />
        </DashboardCard>

        <DashboardCard title="My Followed Projects" actions={<MyItemsProjectsLink />}>
          {sections.followed.length > 0 || (myData.project_keys || []).length > 0 ? (
            <ul className="space-y-2">
              {sections.followed.slice(0, 6).map((item, index) => (
                <MyWorkQueueItem key={`followed-${index}`} item={item} />
              ))}
              {(myData.project_keys || []).slice(0, 6).map((projectKey) => (
                <MyWorkQueueItem key={projectKey} item={{ title: projectKey, project: projectKey }} />
              ))}
            </ul>
          ) : (
            <MyItemsSectionEmpty
              title="No followed projects yet."
              hint="Open Projects to choose work you want to watch."
            />
          )}
        </DashboardCard>
      </DashboardGrid>
    </PrimaryPageLayout>
  )
}

function QueueList({
  items,
  emptyTitle,
  emptyHint,
  showSettingsAction = false,
}: {
  items: MyAttentionItem[]
  emptyTitle: string
  emptyHint?: string
  showSettingsAction?: boolean
}) {
  if (items.length === 0) {
    return (
      <MyItemsSectionEmpty
        title={emptyTitle}
        hint={emptyHint}
        showSettingsAction={showSettingsAction}
      />
    )
  }

  return (
    <ul className="space-y-2">
      {items.slice(0, 6).map((item, index) => (
        <MyWorkQueueItem key={index} item={item} />
      ))}
    </ul>
  )
}

function deriveSections(myData: MyItemsEnvelope) {
  const attention: MyAttentionItem[] = Array.isArray(myData.attention_items) ? myData.attention_items : []

  return {
    actions: listOrFallback(myData.my_action_items, attention, (item) =>
      (item.kind || '').includes('action') || (item.kind || '') === 'my_action',
    ),
    meetings: listOrFallback(myData.my_meetings, attention, (item) => (item.kind || '') === 'meeting'),
    correspondence: listOrFallback(myData.my_correspondence, attention, (item) => (item.kind || '') === 'correspondence'),
    files: listOrFallback(myData.my_files, attention, (item) => (item.kind || '') === 'file'),
    followed: listOrFallback(myData.my_followed_projects, attention, (item) => (item.kind || '') === 'followed_project'),
  }
}

function listOrFallback(
  explicit: MyAttentionItem[] | undefined,
  attention: MyAttentionItem[],
  predicate: (item: MyAttentionItem) => boolean,
) {
  return explicit && explicit.length > 0 ? explicit : attention.filter(predicate)
}
