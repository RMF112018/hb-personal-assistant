import { describe, expect, it } from 'vitest'

import {
  centsToMoneyString,
  formatCurrency,
  formatNumber,
  moneyStringToCents,
  sumMoney,
} from './format'

describe('money BigInt aggregation (exact, no float drift)', () => {
  it('parses money strings to integer cents', () => {
    expect(moneyStringToCents('1234.56')).toBe(123456n)
    expect(moneyStringToCents('-96500.00')).toBe(-9650000n)
    expect(moneyStringToCents('0.1')).toBe(10n)
    expect(moneyStringToCents(null)).toBe(0n)
    expect(moneyStringToCents('')).toBe(0n)
  })

  it('round-trips cents back to a 2-dp money string', () => {
    expect(centsToMoneyString(123456n)).toBe('1234.56')
    expect(centsToMoneyString(-9650000n)).toBe('-96500.00')
    expect(centsToMoneyString(5n)).toBe('0.05')
  })

  it('sums money strings exactly (a case where float would drift)', () => {
    // 0.1 + 0.2 === 0.30000000000000004 in binary float; integer cents is exact.
    expect(sumMoney(['0.10', '0.20'])).toBe('0.30')
    expect(sumMoney(['1000.00', '2500.00', '0.00'])).toBe('3500.00')
    expect(sumMoney(['100000.00', '-96500.00'])).toBe('3500.00')
    expect(sumMoney([])).toBe('0.00')
  })
})

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
