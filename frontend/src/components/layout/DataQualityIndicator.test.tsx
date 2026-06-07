import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DataQualityIndicator } from './DataQualityIndicator'

// Mock the hook so the test is stable (no real react-query, no network, fixed dates)
vi.mock('../../hooks/useDataQualitySummary', () => ({
  useDataQualitySummary: vi.fn(),
}))

import { useDataQualitySummary } from '../../hooks/useDataQualitySummary'

const mockUseDataQualitySummary = vi.mocked(useDataQualitySummary)

function mockSummary(value: {
  data: unknown
  isLoading: boolean
  error: unknown
}) {
  mockUseDataQualitySummary.mockReturnValue(
    value as unknown as ReturnType<typeof useDataQualitySummary>,
  )
}

describe('DataQualityIndicator (Prompt H regression)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders good state with green dot and expected hover title content (normalized last updated)', () => {
    mockSummary({
      data: { status: 'good', last_updated_at: '2026-06-07T20:00:00.000Z', message: 'Sources are current.' },
      isLoading: false,
      error: null,
    })
    const { container } = render(<DataQualityIndicator />)
    expect(screen.getByText('Data Quality')).toBeInTheDocument()
    // Dot should have green class
    const dot = container.querySelector('span.inline-block')
    expect(dot?.className).toContain('bg-green-500')
    // Wrapper title (hover) should contain the mapped label + last updated + message (no raw timestamps asserted exactly)
    const wrapper = container.querySelector('div[title]')
    const title = wrapper?.getAttribute('title') || ''
    expect(title).toContain('Data Quality: Good')
    expect(title).toContain('Last updated:')
    expect(title).toContain('Sources are current.')
  })

  it('renders degraded/unknown as yellow, poor as red, and falls back safely on error/loading', () => {
    mockSummary({
      data: { status: 'degraded', last_updated_at: null, message: 'Some approved sources are stale or pending sync.' },
      isLoading: false,
      error: null,
    })
    const { container: c1 } = render(<DataQualityIndicator />)
    const dot1 = c1.querySelector('span.inline-block')
    expect(dot1?.className).toContain('bg-yellow-500')
    const t1 = c1.querySelector('div[title]')?.getAttribute('title') || ''
    expect(t1).toContain('Needs attention')

    mockSummary({
      data: { status: 'poor', last_updated_at: null, message: 'No approved source data has been collected yet.' },
      isLoading: false,
      error: null,
    })
    const { container: c2 } = render(<DataQualityIndicator />)
    const dot2 = c2.querySelector('span.inline-block')
    expect(dot2?.className).toContain('bg-red-500')
    const t2 = c2.querySelector('div[title]')?.getAttribute('title') || ''
    expect(t2).toContain('Poor')

    // Loading degrades to the same unknown attention state used by stale or pending data.
    mockSummary({ data: null, isLoading: true, error: null })
    const { container: c3 } = render(<DataQualityIndicator />)
    const dot3 = c3.querySelector('span.inline-block')
    expect(dot3?.className).toContain('bg-yellow-500')
  })
})
