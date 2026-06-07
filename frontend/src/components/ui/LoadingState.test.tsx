import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingState } from './LoadingState'

describe('LoadingState', () => {
  it('renders default label', () => {
    render(<LoadingState />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders custom label', () => {
    render(<LoadingState label="Loading Today…" />)
    expect(screen.getByText('Loading Today…')).toBeInTheDocument()
  })
})
