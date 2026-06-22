import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  projectOptionLabel,
  ScheduleProjectPicker,
  type ScheduleProjectOption,
} from './ScheduleProjectPicker'

const projectsMock = vi.fn()

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getScheduleProjects: () => projectsMock(),
    },
  }
})

const duplicateDisplayProjects: ScheduleProjectOption[] = [
  {
    project_key: 'rybovich',
    display_name: '25-745-01 - RYBOVICH-SAFE HARBOR',
    project_number: '25-745-01',
    procore_project_id: '3133242',
    project_identity_label:
      'rybovich — 25-745-01 - RYBOVICH-SAFE HARBOR · #25-745-01 · Procore 3133242 ⚠',
    identity_warning: 'duplicate_display_metadata_across_project_keys',
    selectable_for_import: true,
  },
  {
    project_key: 'tropical',
    display_name: '25-745-01 - RYBOVICH-SAFE HARBOR',
    project_number: '25-745-01',
    procore_project_id: '2525840',
    project_identity_label:
      'tropical — 25-745-01 - RYBOVICH-SAFE HARBOR · #25-745-01 · Procore 2525840 ⚠',
    identity_warning: 'duplicate_display_metadata_across_project_keys',
    selectable_for_import: true,
  },
]

function renderPicker() {
  projectsMock.mockResolvedValue({
    catalog_status: 'ok',
    projects: duplicateDisplayProjects,
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ScheduleProjectPicker
        value=""
        onChange={() => {}}
        importSelectableOnly
        required
      />
    </QueryClientProvider>,
  )
}

describe('projectOptionLabel', () => {
  it('prefixes labels with project_key', () => {
    const label = projectOptionLabel({
      project_key: 'tropical',
      display_name: 'Tropical Wind',
      project_number: 'TWNU18',
      procore_project_id: '2525840',
    })
    expect(label).toBe('tropical — Tropical Wind · #TWNU18 · Procore 2525840')
  })

  it('appends warning marker when identity_warning is set', () => {
    const label = projectOptionLabel({
      project_key: 'rybovich',
      display_name: '25-745-01 - RYBOVICH-SAFE HARBOR',
      project_number: '25-745-01',
      procore_project_id: '3133242',
      identity_warning: 'duplicate_display_metadata_across_project_keys',
    })
    expect(label.endsWith('⚠')).toBe(true)
    expect(label.startsWith('rybovich —')).toBe(true)
  })

  it('prefers API project_identity_label when provided', () => {
    const label = projectOptionLabel({
      project_key: 'tropical',
      project_identity_label: 'tropical — API label',
    })
    expect(label).toBe('tropical — API label')
  })
})

describe('ScheduleProjectPicker', () => {
  it('renders project_key in every selectable option', async () => {
    renderPicker()
    const rybovich = await screen.findByRole('option', { name: /rybovich —/i })
    const tropical = await screen.findByRole('option', { name: /tropical —/i })
    expect(rybovich).toHaveAttribute('value', 'rybovich')
    expect(tropical).toHaveAttribute('value', 'tropical')
    expect(rybovich.textContent).not.toBe(tropical.textContent)
  })
})