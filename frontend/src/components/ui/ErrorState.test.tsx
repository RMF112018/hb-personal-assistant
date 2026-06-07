import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ErrorState } from './ErrorState'

describe('ErrorState', () => {
  it('renders nothing when message is null', () => {
    const { container } = render(<ErrorState message={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders the message text', () => {
    render(<ErrorState message="Something went wrong" />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders a retry button when onRetry is provided and calls it on click', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<ErrorState message="Try again" onRetry={onRetry} />)
    const btn = screen.getByRole('button', { name: /retry/i })
    expect(btn).toBeInTheDocument()
    await user.click(btn)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
