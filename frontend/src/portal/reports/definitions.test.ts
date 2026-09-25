import { describe, expect, it } from 'vitest';

import { CA_COUNTIES } from '@/portal/choices';
import { listFilters, PERIOD_OPTIONS, REPORTS } from './definitions';
import type { ReportSlug } from './types';

/** Every report in the server's registry. */
const SLUGS: ReportSlug[] = ['members', 'aircraft', 'payments', 'reconciliation', 'contributions'];

/**
 * The member report's filter parameters, as `EXPORT_FILTER_PARAMS` in
 * `backend/apps/members/api/admin_filters.py` lists them, less `ordering`, which
 * is the table's sort rather than a filter.
 */
const MEMBER_EXPORT_FILTER_PARAMS = [
  'search',
  'status',
  'certificate',
  'medical',
  'dart',
  'role',
  'expiring_within',
  'is_active',
];

/** The keys of one report's filter fields, in the order they are drawn. */
function keysOf(slug: ReportSlug): string[] {
  return REPORTS[slug].filters.map((field) => field.key);
}

describe('REPORTS', () => {
  it('defines every report the server registers', () => {
    expect(Object.keys(REPORTS).sort()).toEqual([...SLUGS].sort());
  });

  it.each(SLUGS)('files the %s definition under its own slug', (slug) => {
    expect(REPORTS[slug].slug).toBe(slug);
  });

  it.each(SLUGS)('gives each %s filter a key of its own', (slug) => {
    expect(new Set(keysOf(slug)).size).toBe(keysOf(slug).length);
  });

  it('filters members by every export parameter and the county', () => {
    expect([...keysOf('members')].sort()).toEqual(
      [...MEMBER_EXPORT_FILTER_PARAMS, 'county'].sort(),
    );
  });

  it('offers every California county on the member county filter', () => {
    const county = REPORTS.members.filters.find((field) => field.key === 'county');
    expect(county?.options?.map((option) => option.value)).toEqual([...CA_COUNTIES]);
  });

  it('filters aircraft by the register’s own filters', () => {
    expect(keysOf('aircraft')).toEqual([
      'search',
      'make',
      'owner_type',
      'insurance',
      'expiring_within',
    ]);
  });

  it('filters payments by every filter of the finance list', () => {
    expect(keysOf('payments')).toEqual([
      'from',
      'to',
      'provider',
      'status',
      'plan',
      'kind',
      'wallet',
      'reconciled',
      'min_cents',
      'max_cents',
      'search',
      'period',
    ]);
  });

  it('filters reconciliation by dates, provider and grouping', () => {
    expect(keysOf('reconciliation')).toEqual(['from', 'to', 'provider', 'group']);
  });

  it('filters contributions by year', () => {
    expect(keysOf('contributions')).toEqual(['year', 'period']);
  });

  it('lets the columns be chosen only on the three wide reports', () => {
    expect(SLUGS.filter((slug) => REPORTS[slug].choosable)).toEqual([
      'members',
      'aircraft',
      'payments',
    ]);
  });

  it('takes a period only on the payments and contributions reports', () => {
    expect(SLUGS.filter((slug) => REPORTS[slug].periods)).toEqual(['payments', 'contributions']);
  });

  it.each(SLUGS)('offers a period on %s exactly when the report takes one', (slug) => {
    expect(keysOf(slug).includes('period')).toBe(REPORTS[slug].periods);
  });

  it('offers every period on the payments report', () => {
    const period = REPORTS.payments.filters.find((field) => field.key === 'period');
    expect(period?.options).toEqual(PERIOD_OPTIONS);
  });

  it('offers only the whole-year periods on the contributions report', () => {
    const period = REPORTS.contributions.filters.find((field) => field.key === 'period');
    expect(period?.options?.map((option) => option.value)).toEqual(['this_year', 'last_year']);
  });

  it('types and shows the payment amounts in dollars', () => {
    const amounts = REPORTS.payments.filters.filter((field) => field.isDollars === true);
    expect(amounts.map((field) => field.key)).toEqual(['min_cents', 'max_cents']);
  });
});

describe('listFilters', () => {
  it('leaves out the fields only a subscription offers', () => {
    expect(listFilters(REPORTS.payments).map((field) => field.key)).not.toContain('period');
  });

  it('keeps every other field, in order', () => {
    expect(listFilters(REPORTS.members)).toEqual(REPORTS.members.filters);
  });
});
