import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectsPage } from './ProjectsPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[]; queryFn: () => unknown }) => useQueryMock(options),
}))

function renderProjects() {
  return render(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>,
  )
}

function mockProjects(projects: unknown[]) {
  useQueryMock.mockReturnValue({
    data: {
      surface: 'analytics.projects.list',
      projects,
      guardrails: { read_only: true },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })
}

describe('ProjectsPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('queries the project summary endpoint and renders one card per project', () => {
    mockProjects([
      {
        project_key: 'tropical',
        display_name: 'Tropical Resort',
        address: '123 Main St',
        city: 'West Palm Beach',
        state_code: 'FL',
        zip: '33401',
      },
      {
        project_key: 'harbor',
        display_name: 'Harbor Center',
        city: 'Palm Beach',
        state_code: 'FL',
        zip: '33480',
      },
    ])

    renderProjects()

    expect(useQueryMock).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['projects'] }))
    expect(screen.getByRole('heading', { name: 'Projects' })).toBeInTheDocument()
    expect(screen.getByText('Select a project to open its workspace.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Tropical Resort/ })).toHaveAttribute('href', '/projects/tropical')
    expect(screen.getByText('123 Main St · West Palm Beach, FL 33401')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Harbor Center/ })).toHaveAttribute('href', '/projects/harbor')
    expect(screen.getByText('Palm Beach, FL 33480')).toBeInTheDocument()
  })

  it('falls back to project key and handles missing address fields cleanly', () => {
    mockProjects([
      {
        project_key: 'state-only',
        display_name: '',
        state_code: 'FL',
        zip: '33401',
      },
      {
        project_key: 'missing-address',
      },
    ])

    renderProjects()

    expect(screen.getByRole('link', { name: /state-only/ })).toHaveAttribute('href', '/projects/state-only')
    expect(screen.getByText('FL 33401')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /missing-address/ })).toHaveAttribute('href', '/projects/missing-address')
    expect(screen.getByText('Address not available')).toBeInTheDocument()
  })

  it('renders loading state', () => {
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    })

    renderProjects()

    expect(screen.getByText('Loading projects')).toBeInTheDocument()
  })

  it('renders empty state', () => {
    mockProjects([])

    renderProjects()

    expect(screen.getByText('No projects are available yet.')).toBeInTheDocument()
    expect(screen.getByText('Project data will appear after project records are loaded.')).toBeInTheDocument()
  })

  it('renders error state', () => {
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('request failed'),
      refetch: vi.fn(),
    })

    renderProjects()

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Projects could not be loaded. Check the local data connection and try again.',
    )
  })

  it('omits forbidden implementation copy from normal Projects UI', () => {
    mockProjects([
      {
        project_key: 'tropical',
        display_name: 'Tropical Resort',
        address: '123 Main St',
      },
    ])

    renderProjects()

    const text = document.body.textContent || ''
    for (const forbidden of [
      'read model',
      'procore_ep_projects',
      'projection',
      'JSON',
      'raw payload',
      'source package',
      'stack trace',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })
})
