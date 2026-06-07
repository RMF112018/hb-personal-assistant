import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
    // Focusable trigger present (keyboard support)
    const trigger = container.querySelector('span[tabindex="0"]')
    expect(trigger).toBeTruthy()
    // Wrapper title (hover) should contain the mapped label + last updated + message
    const titled = container.querySelector('span[title]')
    const title = titled?.getAttribute('title') || ''
    expect(title).toContain('Data Quality: Good')
    expect(title).toContain('Last updated:')
    expect(title).toContain('Sources are current.')

    // Keyboard focus reveals accessible tooltip (role + content)
    fireEvent.focus(trigger as HTMLElement)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toBeInTheDocument()
    expect(tooltip.textContent || '').toContain('Data Quality: Good')
    expect(tooltip.textContent || '').toContain('Last updated:')
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
    const t1 = c1.querySelector('span[title]')?.getAttribute('title') || ''
    expect(t1).toContain('Needs attention')
    // Focus reveals tooltip role/content for degraded (scoped to this render's container to avoid multi-render accumulation)
    fireEvent.focus(c1.querySelector('span[tabindex="0"]') as HTMLElement)
    const tip1 = c1.querySelector('[role="tooltip"]') as HTMLElement
    expect(tip1.textContent || '').toContain('Needs attention')

    mockSummary({
      data: { status: 'poor', last_updated_at: null, message: 'No approved source data has been collected yet.' },
      isLoading: false,
      error: null,
    })
    const { container: c2 } = render(<DataQualityIndicator />)
    const dot2 = c2.querySelector('span.inline-block')
    expect(dot2?.className).toContain('bg-red-500')
    const t2 = c2.querySelector('span[title]')?.getAttribute('title') || ''
    expect(t2).toContain('Poor')
    fireEvent.focus(c2.querySelector('span[tabindex="0"]') as HTMLElement)
    const tip2 = c2.querySelector('[role="tooltip"]') as HTMLElement
    expect(tip2.textContent || '').toContain('Poor')

    // Loading degrades to the same unknown attention state used by stale or pending data.
    mockSummary({ data: null, isLoading: true, error: null })
    const { container: c3 } = render(<DataQualityIndicator />)
    const dot3 = c3.querySelector('span.inline-block')
    expect(dot3?.className).toContain('bg-yellow-500')
    fireEvent.focus(c3.querySelector('span[tabindex="0"]') as HTMLElement)
    const tip3 = c3.querySelector('[role="tooltip"]') as HTMLElement
    expect(tip3.textContent || '').toContain('Needs attention')
  })
})
