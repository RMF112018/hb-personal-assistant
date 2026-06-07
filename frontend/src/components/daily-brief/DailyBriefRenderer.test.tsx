import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { DailyBriefRenderer } from './DailyBriefRenderer'

function renderBrief(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('DailyBriefRenderer', () => {
  it('renders unavailable copy with Settings action', () => {
    renderBrief(<DailyBriefRenderer status="not_configured" />)

    expect(screen.getByText('Brief not available yet.')).toBeInTheDocument()
    expect(screen.getByText('Check Daily Brief setup in Settings.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Settings' })).toHaveAttribute('href', '/settings')
  })

  it('keeps path and warning details collapsed', () => {
    renderBrief(
      <DailyBriefRenderer
        status="brief_available"
        content="Executive summary"
        path="/tmp/brief.md"
        warnings={['parse warning']}
      />,
    )

    expect(screen.getByText('Executive summary')).toBeInTheDocument()
    expect(screen.getByText('Some brief formatting may need review.')).toBeInTheDocument()
    const details = screen.getByText('Technical details').closest('details')
    expect(details).not.toHaveAttribute('open')
    expect(screen.getByText(/Path: \/tmp\/brief\.md/)).not.toBeVisible()
  })
})
