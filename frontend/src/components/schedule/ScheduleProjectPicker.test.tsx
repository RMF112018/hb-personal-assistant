import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  projectPickerOptionText,
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
    display_name: 'Tropical Wind',
    project_number: '25-745-01',
    procore_project_id: '2525840',
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

describe('projectPickerOptionText', () => {
  it('returns display_name only', () => {
    expect(
      projectPickerOptionText({
        project_key: 'tropical',
        display_name: 'Tropical Wind',
        project_number: 'TWNU18',
        procore_project_id: '2525840',
        project_identity_label: 'tropical — Tropical Wind · #TWNU18 · Procore 2525840',
      }),
    ).toBe('Tropical Wind')
  })

  it('ignores project_identity_label and other identity fields', () => {
    expect(
      projectPickerOptionText({
        project_key: 'rybovich',
        display_name: '25-745-01 - RYBOVICH-SAFE HARBOR',
        project_identity_label: 'rybovich — should not appear',
        identity_warning: 'duplicate_display_metadata_across_project_keys',
      }),
    ).toBe('25-745-01 - RYBOVICH-SAFE HARBOR')
  })

  it('returns empty string when display_name is missing', () => {
    expect(projectPickerOptionText({ project_key: 'legacy-only' })).toBe('')
  })
})

describe('ScheduleProjectPicker', () => {
  it('renders display_name as option text and project_key as value', async () => {
    renderPicker()
    const rybovich = await screen.findByRole('option', {
      name: '25-745-01 - RYBOVICH-SAFE HARBOR',
    })
    const tropical = await screen.findByRole('option', { name: 'Tropical Wind' })
    expect(rybovich).toHaveAttribute('value', 'rybovich')
    expect(tropical).toHaveAttribute('value', 'tropical')
    expect(rybovich.textContent).toBe('25-745-01 - RYBOVICH-SAFE HARBOR')
    expect(tropical.textContent).toBe('Tropical Wind')
  })
})