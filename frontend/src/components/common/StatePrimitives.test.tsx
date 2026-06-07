import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'

import { DisconnectedState } from './DisconnectedState'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'
import { TechnicalDetails } from './TechnicalDetails'

describe('common state primitives', () => {
  it('renders loading, empty, and disconnected states with action slots', () => {
    render(
      <>
        <LoadingState actions={<button>Cancel</button>} />
        <EmptyState title="No signals" hint="Connect sources" actions={<button>Open Settings</button>} />
        <DisconnectedState actions={<button>Connect</button>} />
      </>,
    )

    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.getByText('No signals')).toBeInTheDocument()
    expect(screen.getByText('Connect sources')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open Settings' })).toBeInTheDocument()
    expect(screen.getByText('Connection needed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Connect' })).toBeInTheDocument()
  })

  it('keeps technical details collapsed by default', () => {
    render(<TechnicalDetails summary="Technical details" details="500 internal route detail" />)

    const details = screen.getByText('Technical details').closest('details')
    expect(details).not.toHaveAttribute('open')
    expect(screen.getByText('500 internal route detail')).not.toBeVisible()
  })

  it('renders safe error copy with retry and hidden raw detail', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<ErrorState message="500 raw_backend_trace" onRetry={onRetry} />)

    expect(screen.getByText('We could not load this section.')).toBeInTheDocument()
    expect(screen.queryByText('500 raw_backend_trace')).not.toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
