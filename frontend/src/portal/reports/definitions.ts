/**
 * Every report the portal can filter, download, and subscribe somebody to.
 *
 * This is the one list of each report's filter fields.  A list page draws
 * `listFilters(REPORTS.<slug>)` in its `FilterBar`; the subscription form draws
 * `REPORTS.<slug>.filters`, which also holds the fields only a subscription
 * offers, such as the period a scheduled report covers.  Each field's key is
 * the query parameter the report's list and export endpoints read.
 */
import {
  CA_COUNTIES,
  PAYMENT_PROVIDER_LABELS,
  PAYMENT_STATUS_LABELS,
  PAYMENT_WALLET_LABELS,
  ROLE_CHOICES,
} from '@/portal/choices';
import { KIND_LABELS } from '@/portal/features/admin-payments/labels';
import {
  CERTIFICATE_FILTER_CHOICES,
  MEDICAL_FILTER_CHOICES,
  STATUS_CHOICES,
} from '@/portal/features/admin-members/choices';
import { OWNER_TYPE_LABELS, OWNER_TYPES } from '@/portal/features/aircraft/form';
import type { FilterField, Option, ReportDefinition, ReportSlug } from './types';

/** How many earlier years the contributions report offers besides the current one. */
const EARLIER_YEARS_OFFERED = 9;

/** The periods a dated report resolves on the day it is built, as the server names them. */
export const PERIOD_OPTIONS: readonly Option[] = [
  { value: 'this_month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
  { value: 'this_year', label: 'This year' },
  { value: 'last_year', label: 'Last year' },
];

/** A `{code: label}` record as options, in the order `codes` lists them. */
function optionsFor<Code extends string>(
  codes: readonly Code[],
  labels: Record<Code, string>,
): Option[] {
  return codes.map((code) => ({ value: code, label: labels[code] }));
}

/** The period field of a report that takes `?period=`, offered only to subscriptions. */
function periodField(options: readonly Option[], placeholder: string): FilterField {
  return {
    key: 'period',
    label: 'Period',
    kind: 'select',
    options,
    placeholder,
    subscriptionOnly: true,
  };
}

/** The years before this one, most recent first: the blank choice is this year. */
function earlierYears(today: Date = new Date()): Option[] {
  return Array.from({ length: EARLIER_YEARS_OFFERED }, (_unused, back) => {
    const year = String(today.getFullYear() - 1 - back);
    return { value: year, label: year };
  });
}

const PROVIDER_OPTIONS = optionsFor(
  ['stripe', 'paypal', 'mock', 'manual'],
  PAYMENT_PROVIDER_LABELS,
);

const COUNTY_OPTIONS: Option[] = CA_COUNTIES.map((county) => ({
  value: county,
  label: county,
}));

const MEMBER_FILTERS: FilterField[] = [
  {
    key: 'search',
    label: 'Search',
    kind: 'search',
    placeholder: 'Name, email, phone, or certificate',
  },
  // "Any" on its own, never "Any status": a filter that is not set takes in
  // the members who answered "none" as well as those who answered.
  { key: 'status', label: 'Membership', kind: 'select', options: STATUS_CHOICES },
  { key: 'certificate', label: 'Certificate', kind: 'select', options: CERTIFICATE_FILTER_CHOICES },
  { key: 'medical', label: 'Medical', kind: 'select', options: MEDICAL_FILTER_CHOICES },
  // The DARTs are the server's, so the page supplies them through `options`.
  { key: 'dart', label: 'DART', kind: 'select' },
  { key: 'county', label: 'County', kind: 'select', options: COUNTY_OPTIONS },
  { key: 'role', label: 'Role', kind: 'select', options: ROLE_CHOICES },
  { key: 'expiring_within', label: 'Expiring within (days)', kind: 'number' },
  { key: 'is_active', label: 'Active accounts only', kind: 'toggle' },
];

const AIRCRAFT_FILTERS: FilterField[] = [
  { key: 'search', label: 'Search', kind: 'search', hint: 'N-number, make, model, or owner.' },
  { key: 'make', label: 'Make', kind: 'search' },
  {
    key: 'owner_type',
    label: 'Owner type',
    kind: 'select',
    placeholder: 'Any owner type',
    options: optionsFor(OWNER_TYPES, OWNER_TYPE_LABELS),
  },
  {
    key: 'insurance',
    label: 'Insurance',
    kind: 'select',
    placeholder: 'Any insurance state',
    options: [
      { value: 'current', label: 'Current' },
      { value: 'expired', label: 'Expired' },
      { value: 'missing', label: 'Not on file' },
    ],
  },
  {
    key: 'expiring_within',
    label: 'Expiring within',
    kind: 'select',
    placeholder: 'Any expiry',
    options: [
      { value: '30', label: 'Expiring in 30 days' },
      { value: '60', label: 'Expiring in 60 days' },
      { value: '90', label: 'Expiring in 90 days' },
    ],
  },
];

const PAYMENT_FILTERS: FilterField[] = [
  { key: 'from', label: 'From', kind: 'date' },
  { key: 'to', label: 'To', kind: 'date' },
  {
    key: 'provider',
    label: 'Provider',
    kind: 'select',
    placeholder: 'Any provider',
    options: PROVIDER_OPTIONS,
  },
  {
    key: 'status',
    label: 'Status',
    kind: 'select',
    placeholder: 'Any status',
    options: optionsFor(
      ['succeeded', 'pending', 'failed', 'partially_refunded', 'refunded'],
      PAYMENT_STATUS_LABELS,
    ),
  },
  // The plans are the server's, so the page supplies them through `options`.
  { key: 'plan', label: 'Plan', kind: 'select', placeholder: 'Any plan' },
  {
    key: 'kind',
    label: 'For',
    kind: 'select',
    placeholder: 'Dues or gifts',
    options: optionsFor(['membership', 'contribution', 'both'], KIND_LABELS),
  },
  {
    key: 'wallet',
    label: 'Method',
    kind: 'select',
    placeholder: 'Any method',
    options: optionsFor(
      [
        'card',
        'apple_pay',
        'google_pay',
        'link',
        'paypal',
        'check',
        'cash',
        'bank_transfer',
        'other',
      ],
      PAYMENT_WALLET_LABELS,
    ),
  },
  {
    key: 'reconciled',
    label: 'Reconciled',
    kind: 'select',
    placeholder: 'Matched or not',
    options: [
      { value: 'yes', label: 'Matched' },
      { value: 'no', label: 'Not matched' },
    ],
  },
  { key: 'min_cents', label: 'At least', kind: 'number', placeholder: 'Dollars', isDollars: true },
  { key: 'max_cents', label: 'At most', kind: 'number', placeholder: 'Dollars', isDollars: true },
  {
    key: 'search',
    label: 'Search',
    kind: 'search',
    placeholder: 'Name, email, reference, or note',
  },
  periodField(PERIOD_OPTIONS, 'Any date'),
];

const RECONCILIATION_FILTERS: FilterField[] = [
  { key: 'from', label: 'From', kind: 'date' },
  { key: 'to', label: 'To', kind: 'date' },
  {
    key: 'provider',
    label: 'Provider',
    kind: 'select',
    placeholder: 'Any provider',
    options: PROVIDER_OPTIONS,
  },
  // Blank is the server's own grouping, by month.
  {
    key: 'group',
    label: 'Rows',
    kind: 'select',
    placeholder: 'By month',
    options: [
      { value: 'year', label: 'By year' },
      { value: 'provider', label: 'By provider' },
    ],
  },
];

const CONTRIBUTION_FILTERS: FilterField[] = [
  // Blank is the server's own choice, the current calendar year.
  { key: 'year', label: 'Year', kind: 'select', placeholder: 'This year', options: earlierYears() },
  periodField(
    PERIOD_OPTIONS.filter((option) => option.value.endsWith('_year')),
    'The year chosen',
  ),
];

const EMAIL_LOG_FILTERS: FilterField[] = [
  // The purposes are the server's, so the panel supplies them through `options`.
  { key: 'purpose', label: 'Purpose', kind: 'select', placeholder: 'Any purpose' },
  {
    key: 'status',
    label: 'Status',
    kind: 'select',
    placeholder: 'Any status',
    options: [
      { value: 'sent', label: 'Sent' },
      { value: 'failed', label: 'Failed' },
    ],
  },
  { key: 'from', label: 'From', kind: 'date' },
  { key: 'to', label: 'To', kind: 'date' },
  { key: 'q', label: 'Search', kind: 'search', placeholder: 'Name or address' },
];

/** Every report, by slug. */
export const REPORTS: Readonly<Record<ReportSlug, ReportDefinition>> = {
  members: {
    slug: 'members',
    label: 'Members',
    filters: MEMBER_FILTERS,
    choosable: true,
    periods: false,
  },
  aircraft: {
    slug: 'aircraft',
    label: 'Aircraft',
    filters: AIRCRAFT_FILTERS,
    choosable: true,
    periods: false,
  },
  payments: {
    slug: 'payments',
    label: 'Payments',
    filters: PAYMENT_FILTERS,
    choosable: true,
    periods: true,
  },
  reconciliation: {
    slug: 'reconciliation',
    label: 'Reconciliation',
    filters: RECONCILIATION_FILTERS,
    choosable: false,
    periods: false,
  },
  contributions: {
    slug: 'contributions',
    label: 'Contributions',
    filters: CONTRIBUTION_FILTERS,
    choosable: false,
    periods: true,
  },
  emails: {
    slug: 'emails',
    label: 'Email log',
    filters: EMAIL_LOG_FILTERS,
    choosable: true,
    periods: false,
  },
};

/**
 * The fields a report's list page draws: every one but those only a
 * subscription offers.
 *
 * @param definition the report whose list page is filtering.
 * @returns its filter fields in order, less the subscription-only ones.
 */
export function listFilters(definition: ReportDefinition): FilterField[] {
  return definition.filters.filter((field) => field.subscriptionOnly !== true);
}
