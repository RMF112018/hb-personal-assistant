import { describe, expect, it } from 'vitest'

import { formatCurrency, formatNumber } from './format'

describe('formatCurrency', () => {
  it('formats decimal strings as whole-dollar USD', () => {
    expect(formatCurrency('1234567.89')).toBe('$1,234,568')
    expect(formatCurrency('500.00')).toBe('$500')
  })

  it('formats negative variances with a leading minus', () => {
    expect(formatCurrency('-10.00')).toBe('-$10')
  })

  it('accepts numbers as well as strings', () => {
    expect(formatCurrency(2500)).toBe('$2,500')
  })

  it('returns an em-dash for null, empty, or non-numeric input', () => {
    expect(formatCurrency(null)).toBe('—')
    expect(formatCurrency(undefined)).toBe('—')
    expect(formatCurrency('')).toBe('—')
    expect(formatCurrency('n/a')).toBe('—')
  })

  it('is consistent across repeated calls on the same value', () => {
    expect(formatCurrency('500.00')).toBe(formatCurrency('500.00'))
  })
})

describe('formatNumber', () => {
  it('groups thousands', () => {
    expect(formatNumber('12000')).toBe('12,000')
    expect(formatNumber(42)).toBe('42')
  })

  it('returns an em-dash for null, empty, or non-numeric input', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber('')).toBe('—')
    expect(formatNumber('abc')).toBe('—')
  })
})
