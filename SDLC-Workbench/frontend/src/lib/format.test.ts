import { describe, expect, it } from 'vitest'
import { count, money, seconds, shortDate } from './format'

describe('money', () => {
  it('unknown money is "unknown", never zero', () => {
    expect(money(null)).toBe('unknown')
    expect(money(undefined)).toBe('unknown')
    expect(money(Number.NaN)).toBe('unknown')
    expect(money(Number.POSITIVE_INFINITY)).toBe('unknown')
  })
  it('a known zero is $0.00, which is different from unknown', () => {
    expect(money(0)).toBe('$0.00')
    expect(money(0)).not.toBe(money(null))
  })
  it('keeps enough digits for tiny amounts and trims large ones', () => {
    expect(money(0.00329)).toBe('$0.00329')
    expect(money(0.01467)).toBe('$0.0147')
    expect(money(0.2057)).toBe('$0.2057')
    expect(money(2)).toBe('$2.00')
    expect(money(12.3456)).toBe('$12.35')
  })
})

describe('other formatters', () => {
  it('counts with the right plural', () => {
    expect(count(1, 'phase')).toBe('1 phase')
    expect(count(0, 'phase')).toBe('0 phases')
    expect(count(7, 'phase')).toBe('7 phases')
    expect(count(2, 'person', 'people')).toBe('2 people')
  })
  it('a date is short and a non-date is shown as given, never "Invalid Date"', () => {
    expect(shortDate('2026-10-29T08:00:00.000Z')).toBe('29 Oct 2026')
    expect(shortDate('not a date')).toBe('not a date')
    expect(shortDate('')).toBe('')
  })
  it('durations read naturally and a bad one is unknown', () => {
    expect(seconds(1.25)).toBe('1.3 s')
    expect(seconds(59.4)).toBe('59 s')
    expect(seconds(77.3)).toBe('1 min 17 s')    // from 60 seconds it switches to minutes
    expect(seconds(125)).toBe('2 min 5 s')
    expect(seconds(-1)).toBe('unknown')
    expect(seconds(Number.NaN)).toBe('unknown')
  })
})
