import { describe, expect, it } from 'vitest'

import { getErrorCopy, safeDisplayText } from './errorCopy'
import {
  getAuthStatusCopy,
  getConfidenceCopy,
  getDataQualityCopy,
  getFreshnessCopy,
} from './statusCopy'

describe('statusCopy', () => {
  it('maps known backend statuses to user-facing copy', () => {
    expect(getAuthStatusCopy('connected_stale_reauth_required')).toMatchObject({
      label: 'Reconnect required',
      tone: 'danger',
    })
    expect(getFreshnessCopy('fresh')).toMatchObject({ label: 'Fresh', tone: 'success' })
    expect(getConfidenceCopy('not_available')).toMatchObject({ label: 'Limited data' })
    expect(getDataQualityCopy('degraded')).toMatchObject({ label: 'Needs attention' })
  })

  it('falls back safely for unknown statuses', () => {
    expect(getAuthStatusCopy('backend_only_status')).toMatchObject({
      label: 'Unknown',
      tone: 'neutral',
    })
  })
})

describe('errorCopy', () => {
  it('maps raw errors to safe user messages with retained technical detail', () => {
    const copy = getErrorCopy(new Error('500 raw_backend_trace'))

    expect(copy.userMessage).toBe('We could not load this section.')
    expect(copy.technicalDetail).toBe('500 raw_backend_trace')
  })

  it('maps known backend detail to safe specific copy', () => {
    expect(getErrorCopy('invalid_ui_role').userMessage).toBe('You do not have access to this view.')
  })

  it('extracts display text without JSON stringifying objects', () => {
    expect(safeDisplayText({ title: 'Meeting prep' })).toBe('Meeting prep')
    expect(safeDisplayText({ route: '/api/raw' })).toBe('Details unavailable')
  })
})
