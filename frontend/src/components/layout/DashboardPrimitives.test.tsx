import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SectionCard } from '../common/SectionCard'
import { DashboardCard } from './DashboardCard'
import { DashboardGrid } from './DashboardGrid'
import { PrimaryPageLayout } from './PrimaryPageLayout'

describe('dashboard layout primitives', () => {
  it('renders a primary page visual label (non-heading), status row, actions, and content', () => {
    render(
      <PrimaryPageLayout
        title="Today"
        subtitle="Current advisory signals"
        status={<span>Fresh</span>}
        actions={<button>Refresh</button>}
      >
        <p>Page content</p>
      </PrimaryPageLayout>,
    )

    // Primary title is now a visual label (div), not a heading. Canonical h1 lives in shell PageHeader.
    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Current advisory signals')).toBeInTheDocument()
    expect(screen.getByText('Fresh')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument()
    expect(screen.getByText('Page content')).toBeInTheDocument()
  })

  it('renders dashboard grid classes without dense auto flow', () => {
    const { container } = render(
      <DashboardGrid columns="metrics" gap="lg">
        <div>Metric</div>
      </DashboardGrid>,
    )

    const grid = container.firstElementChild
    expect(grid).toHaveClass('grid')
    expect(grid).toHaveClass('xl:grid-cols-4')
    expect(grid).toHaveClass('gap-4')
    expect(grid?.className).not.toContain('grid-flow-dense')
  })

  it('supports card span variants while preserving DOM reading order', () => {
    const { container } = render(
      <DashboardGrid>
        <DashboardCard title="First" span="wide">A</DashboardCard>
        <DashboardCard title="Second">B</DashboardCard>
      </DashboardGrid>,
    )

    const headings = screen.getAllByRole('heading').map((heading) => heading.textContent)
    expect(headings).toEqual(['First', 'Second'])
    expect(container.querySelector('article')).toHaveClass('md:col-span-2')
  })

  it('renders section card slots with semantic heading', () => {
    render(
      <SectionCard
        title="Action Items"
        description="Filtered queue"
        actions={<button>Open</button>}
        footer={<span>Advisory only</span>}
      >
        <p>Queue content</p>
      </SectionCard>,
    )

    expect(screen.getByRole('heading', { name: 'Action Items' })).toBeInTheDocument()
    expect(screen.getByText('Filtered queue')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open' })).toBeInTheDocument()
    expect(screen.getByText('Queue content')).toBeInTheDocument()
    expect(screen.getByText('Advisory only')).toBeInTheDocument()
  })
})
