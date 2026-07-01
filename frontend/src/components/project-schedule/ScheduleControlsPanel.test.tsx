import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ScheduleControlsPanel } from './ScheduleControlsPanel'

const baseControls = {
  available: true,
  as_of_date: '2026-07-03',
  schedule_data_date: '2026-06-23',
  summary: {
    overall_status: 'review',
    headline: 'Schedule controls recommend PM review.',
    supporting_points: ['Quality trust status: degraded.'],
  },
  sections: {
    identity_trust: {
      available: true,
      identity_trust_status: 'trusted',
      headline: 'Schedule identity is trusted for PM review.',
    },
    analytics_trust: {
      available: true,
      analytics_trust_status: 'degraded',
      failure_message_redacted: 'CPM completed with warnings.',
    },
    logic_integrity: {
      available: true,
      label: 'Logic integrity',
      status: 'degraded',
      headline: '1 measured check(s) are in warning range for this group.',
      metrics: [{ label: 'Logic integrity', resolved_status: 'warn', counts: [{ label: 'Open starts', count: 2 }] }],
    },
    constraints: {
      available: true,
      label: 'Constraint quality',
      status: 'ready',
      headline: 'Measured checks in this group are within thresholds.',
      metrics: [],
    },
    float_quality: { available: true, label: 'Float quality', status: 'ready', headline: 'OK', metrics: [] },
    duration_quality: { available: true, label: 'Duration quality', status: 'ready', headline: 'OK', metrics: [] },
    date_quality: { available: true, label: 'Date quality', status: 'ready', headline: 'OK', metrics: [] },
    critical_path_readiness: {
      available: true,
      label: 'Critical path readiness',
      status: 'degraded',
      headline: 'Critical-path analytics are not fully ready.',
      metrics: [],
    },
    cost_resource_readiness: {
      available: true,
      label: 'Cost and resource readiness',
      status: 'ready',
      headline: 'Available',
      metrics: [],
    },
    baseline_readiness: {
      available: true,
      label: 'Baseline readiness',
      status: 'unavailable',
      headline: 'Baseline comparison analytics are not ready.',
      metrics: [],
    },
    capability_limitations: {
      available: true,
      items: [
        'Out-of-sequence progress analysis is not implemented in this release; do not treat schedule movement as entitlement or causation.',
      ],
    },
    cpm_observability: { available: true, headline: 'CPM recompute succeeded for the selected schedule version.' },
  },
  quality_controls: {
    quality_trust_status: 'degraded',
    quality_run_status: 'complete',
    scorecard: { overall_score: '82.0', quality_grade: 'B' },
    recommended_pm_actions: ['Review logic integrity counts and confirm whether open ends need cleanup.'],
    capability_limitations: [
      'Out-of-sequence progress analysis is not implemented in this release; do not treat schedule movement as entitlement or causation.',
    ],
  },
  top_controls: [
    {
      control_id: 'quality-group:logic_integrity',
      category: 'quality',
      severity: 'review',
      confidence: 'high',
      title: 'Logic integrity',
      summary: '1 measured check(s) are in warning range for this group.',
      recommended_action: 'Review the quality control group metrics before relying on comparisons.',
      links: { review_item: '/projects/tropical/schedule/workbench' },
    },
  ],
  links: { review_workbench: '/projects/tropical/schedule/workbench' },
}

describe('ScheduleControlsPanel', () => {
  it('renders quality scorecard and control groups', () => {
    render(
      <MemoryRouter>
        <ScheduleControlsPanel controls={baseControls} comparisonBasis="prior_update" onComparisonBasisChange={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Quality scorecard')).toBeInTheDocument()
    expect(screen.getAllByText(/Logic integrity/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Capability limitations/i)).toBeInTheDocument()
    expect(screen.getByText(/Out-of-sequence progress analysis is not implemented/i)).toBeInTheDocument()
    expect(screen.getByText(/Identity trust/i)).toBeInTheDocument()
    expect(screen.queryByText(/schedule_version_key/i)).not.toBeInTheDocument()
  })

  it('renders identity-blocked posture copy', () => {
    const blocked = {
      ...baseControls,
      summary: {
        overall_status: 'critical',
        headline: 'Schedule controls are blocked by identity, analytics, or quality trust gates.',
        supporting_points: [],
      },
      sections: {
        ...baseControls.sections,
        identity_trust: {
          available: true,
          identity_trust_status: 'mismatch',
          headline: 'Schedule identity does not match the linked project.',
        },
      },
      quality_controls: {
        ...baseControls.quality_controls,
        quality_trust_status: 'blocked',
      },
    }
    render(
      <MemoryRouter>
        <ScheduleControlsPanel controls={blocked} comparisonBasis="prior_update" onComparisonBasisChange={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/blocked by identity/i)).toBeInTheDocument()
    expect(screen.getByText(/does not match the linked project/i)).toBeInTheDocument()
  })
})
