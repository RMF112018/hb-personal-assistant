import { describe, expect, it } from 'vitest'

import { PRIMARY_NAV, getRouteTitleForPath } from './navigationModel'

describe('navigationModel schedules module', () => {
  it('includes Schedules as a top-level primary nav item', () => {
    const labels = PRIMARY_NAV.map((item) => item.label)
    expect(labels).toContain('Schedules')
    expect(PRIMARY_NAV.find((item) => item.label === 'Schedules')?.route).toBe('/schedules')
  })

  it('resolves titles for /schedules routes', () => {
    expect(getRouteTitleForPath('/schedules/imports')).toBe('Schedule Imports')
    expect(getRouteTitleForPath('/schedules/versions')).toBe('Schedule Versions')
    expect(getRouteTitleForPath('/schedules/activities')).toBe('Schedule Activities')
    expect(getRouteTitleForPath('/schedules/quality')).toBe('Schedule Health')
    expect(getRouteTitleForPath('/schedules/health')).toBe('Schedule Health')
    expect(getRouteTitleForPath('/schedules/version-diff')).toBe('Schedule Version Diff')
    expect(getRouteTitleForPath('/schedules/cost-mapping')).toBe('Schedule Cost Mapping')
    expect(getRouteTitleForPath('/schedules/cost-weighting')).toBe('Schedule Cost Weighting')
  })
})
