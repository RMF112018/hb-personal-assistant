import { describe, expect, it } from 'vitest'

import {
  isScheduleResponseStale,
  metricPanelUiState,
  scheduleQueryKeySuffix,
} from './scheduleDataState'

describe('scheduleDataState', () => {
  it('suffixes latest when as_of is empty', () => {
    expect(scheduleQueryKeySuffix('')).toBe('latest')
    expect(scheduleQueryKeySuffix('2026-06-22')).toBe('2026-06-22')
  })

  it('detects stale retained summary during as_of refresh', () => {
    expect(
      isScheduleResponseStale({ as_of_date: '2026-06-22' }, '2026-06-29', true),
    ).toBe(true)
    expect(
      isScheduleResponseStale({ as_of_date: '2026-06-29' }, '2026-06-29', true),
    ).toBe(false)
  })

  it('does not classify metric panel as unavailable while refreshing', () => {
    expect(
      metricPanelUiState(undefined, { isFetching: true, hasData: true }),
    ).toBe('refreshing')
  })
})
