import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ForecastDialog } from './ForecastDialog'

const onClose = vi.fn()

function renderDialog(open: boolean) {
  return render(
    <ForecastDialog open={open} onClose={onClose} title="Create forecast">
      <p>Body content</p>
      <button type="button">Inside button</button>
    </ForecastDialog>,
  )
}

describe('ForecastDialog', () => {
  beforeEach(() => {
    onClose.mockClear()
  })

  it('renders nothing when closed', () => {
    const { container } = renderDialog(false)
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders the dialog when open', () => {
    renderDialog(true)
    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText('Create forecast')).toBeInTheDocument()
    expect(screen.getByText('Body content')).toBeInTheDocument()
  })

  it('closes on Escape', () => {
    renderDialog(true)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on backdrop click', () => {
    const { container } = renderDialog(true)
    const backdrop = container.querySelector('.forecast-dialog-backdrop') as HTMLElement
    expect(backdrop).not.toBeNull()
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not close on clicks inside the dialog', () => {
    renderDialog(true)
    fireEvent.click(screen.getByText('Inside button'))
    fireEvent.click(screen.getByText('Body content'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('closes when the header close button is clicked', () => {
    renderDialog(true)
    fireEvent.click(screen.getByLabelText('Close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
