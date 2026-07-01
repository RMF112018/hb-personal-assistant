import { describe, expect, it } from 'vitest'

import {
  driverDetailHref,
  isAllowedControlsComparisonBasis,
  labelForComparisonBasis,
  normalizeBaselineContext,
  SCHEDULE_CONTROLS_COMPARISON_BASIS_VALUES,
  workbenchHref,
} from './scheduleBaselineLabels'

describe('scheduleBaselineLabels', () => {
  it('labels named comparison basis values for PM display', () => {
    expect(labelForComparisonBasis('current_contract_baseline')).toBe('Current Contract Baseline')
    expect(labelForComparisonBasis('prior_update')).toBe('Prior Update')
  })

  it('recognizes allowed controls basis values only', () => {
    for (const basis of SCHEDULE_CONTROLS_COMPARISON_BASIS_VALUES) {
      expect(isAllowedControlsComparisonBasis(basis)).toBe(true)
    }
    expect(isAllowedControlsComparisonBasis('baseline')).toBe(true)
    expect(isAllowedControlsComparisonBasis('mystery_basis')).toBe(false)
  })

  it('normalizes baseline_context across controls and workbench shapes', () => {
    const controls = normalizeBaselineContext({
      slot_label: 'Current Contract Baseline',
      baseline_schedule_version_key: 'tropical|S1|2026-06-01',
      baseline_schedule_data_date: '2026-06-01',
      baseline_display_name: 'Contract baseline',
      selection_status: 'selected',
    })
    const workbench = normalizeBaselineContext({
      slot_label: 'Current Contract Baseline',
      schedule_version_key: 'tropical|S1|2026-06-01',
      schedule_data_date: '2026-06-01',
      display_name: 'Contract baseline',
      selection_status: 'selected',
    })
    expect(controls.versionKey).toBe(workbench.versionKey)
    expect(controls.slotLabel).toBe(workbench.slotLabel)
  })

  it('builds workbench and driver hrefs with comparison_basis and as_of', () => {
    expect(
      workbenchHref('tropical', {
        asOf: '2026-07-03',
        comparisonBasis: 'current_contract_baseline',
      }),
    ).toBe('/projects/tropical/schedule/workbench?comparison_basis=current_contract_baseline&as_of=2026-07-03')
    const href = driverDetailHref('tropical', 'DRV-A', {
      asOf: '2026-07-03',
      comparisonBasis: 'current_contract_baseline',
    })
    expect(href).toContain('comparison_basis=current_contract_baseline')
    expect(href).toContain('/schedule/driver-detail?')
    expect(href).toContain('activity_id=DRV-A')
    expect(href).not.toContain('/schedule/drivers/DRV-A')
  })

  it('encodes slash-bearing activity IDs as query param not path segment', () => {
    const href = driverDetailHref('tropical', 'FAB/DEL-10', {
      asOf: '2026-07-03',
      comparisonBasis: 'current_contract_baseline',
    })
    expect(href).toBe(
      '/projects/tropical/schedule/driver-detail?activity_id=FAB%2FDEL-10&comparison_basis=current_contract_baseline&as_of=2026-07-03',
    )
    expect(href).not.toMatch(/\/schedule\/drivers\/FAB/)
  })
})
