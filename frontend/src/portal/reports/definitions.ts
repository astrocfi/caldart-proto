/**
 * Every report the portal can filter, download, and subscribe somebody to.
 *
 * This is the one list of each report's filter fields.  A list page draws
 * `listFilters(REPORTS.<slug>)` in its `FilterBar`; the subscription form draws
 * `REPORTS.<slug>.filters`, which also holds the fields only a subscription
 * offers, such as the period a scheduled report covers; the subscription form draws
 * `subscriptionFilters(REPORTS.<slug>)`, which leaves out the fields only a list page
 * offers.  Each field's key is the query parameter the report's list and export
 * endpoints read.
 */
import {
  ACCOUNT_KIND_LABELS,
  CA_COUNTIES,
  PAYMENT_PROVIDER_LABELS,
  PAYMENT_STATUS_LABELS,
  PAYMENT_WALLET_LABELS,
  ROLE_CHOICES,
} from '@/portal/choices';
import {
  KIND_LABELS,
  MANDATE_KIND_LABELS,
  MANDATE_STATUS_LABELS,
} from '@/portal/features/admin-payments/labels';
import {
  CERTIFICATE_FILTER_CHOICES,
  KIND_FILTER_CHOICES,
  MEDICAL_FILTER_CHOICES,
  STATUS_CHOICES,
} from '@/portal/features/admin-members/choices';
import {
  AIRWORTHINESS_LABELS,
  AIRWORTHINESS_VALUES,
  CATEGORIES,
  CATEGORY_LABELS,
} from '@/portal/features/aircraft/categories';
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
    key: 'kind',
    label: 'Kind',
    kind: 'select',
    placeholder: 'Any kind',
    options: KIND_FILTER_CHOICES,
  },
  {
    key: 'search',
    label: 'Search',
    kind: 'search',
    placeholder: 'Name, email, or phone',
    hint: 'Search by name, email, phone, or certificate number.',
  },
  // "Any" on its own, never "Any status": a filter that is not set takes in
  // the members who answered "none" as well as those who answered.
  { key: 'status', label: 'Membership', kind: 'select', options: STATUS_CHOICES },
  { key: 'certificate', label: 'Certificate', kind: 'select', options: CERTIFICATE_FILTER_CHOICES },
  { key: 'medical', label: 'Medical', kind: 'select', options: MEDICAL_FILTER_CHOICES },
  // The DARTs are the server's, so the page supplies them through `options`.
  { key: 'dart', label: 'DART', kind: 'select' },
  // Several counties at once: a DART that covers two counties asks for both.
  {
    key: 'county',
    label: 'County',
    kind: 'multiselect',
    options: COUNTY_OPTIONS,
    hint: 'Check as many counties as you like.',
  },
  { key: 'role', label: 'Role', kind: 'select', options: ROLE_CHOICES },
  { key: 'expiring_within', label: 'Expiring within (days)', kind: 'number' },
];

// The roles report has a section for every role but member, so member is no choice.
const ROLE_FILTERS: FilterField[] = [
  { key: 'search', label: 'Search', kind: 'search', placeholder: 'Name or email' },
  {
    key: 'role',
    label: 'Role',
    kind: 'select',
    placeholder: 'Any role',
    options: ROLE_CHOICES.filter((choice) => choice.value !== 'member'),
  },
  // A donor never holds a role.
  {
    key: 'kind',
    label: 'Kind',
    kind: 'select',
    placeholder: 'Any kind',
    options: optionsFor(['member', 'friend'], ACCOUNT_KIND_LABELS),
  },
];

const VERIFICATION_FILTERS: FilterField[] = [
  // Blank is the server's own default, the items not yet verified.
  {
    key: 'status',
    label: 'Status',
    kind: 'select',
    placeholder: 'Not verified',
    options: [
      { value: 'verified', label: 'Verified' },
      { value: 'all', label: 'All' },
    ],
  },
  // The DARTs are the server's, so the page supplies them through `options`.
  { key: 'dart', label: 'DART', kind: 'select', placeholder: 'Any DART' },
];

const AIRCRAFT_FILTERS: FilterField[] = [
  { key: 'search', label: 'Search', kind: 'search', hint: 'N-number, make, model, or owner.' },
  { key: 'make', label: 'Make', kind: 'search' },
  {
    key: 'category',
    label: 'Category',
    kind: 'select',
    placeholder: 'Any category',
    options: optionsFor(CATEGORIES, CATEGORY_LABELS),
  },
  {
    key: 'airworthiness',
    label: 'Airworthiness',
    kind: 'select',
    placeholder: 'Any airworthiness',
    options: optionsFor(AIRWORTHINESS_VALUES, AIRWORTHINESS_LABELS),
  },
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
      // The words the register's insurance dot shows, so a filter and a row agree.
      { value: 'current', label: 'Insured' },
      { value: 'expired', label: 'Insurance expired' },
      { value: 'missing', label: 'No insurance on file' },
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
    placeholder: 'Membership or contribution',
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
    placeholder: 'Any',
    options: [
      { value: 'yes', label: 'Reconciled' },
      { value: 'no', label: 'Not reconciled' },
    ],
  },
  { key: 'min_cents', label: 'At least', kind: 'number', isDollars: true },
  { key: 'max_cents', label: 'At most', kind: 'number', isDollars: true },
  {
    key: 'search',
    label: 'Search',
    kind: 'search',
    placeholder: 'Name, email, or reference',
    hint: 'Search by name, email, reference, or note.',
  },
  periodField(PERIOD_OPTIONS, 'Any date'),
];

const RENEWAL_FILTERS: FilterField[] = [
  {
    key: 'status',
    label: 'Status',
    kind: 'select',
    placeholder: 'Any status',
    options: optionsFor(['active', 'pending', 'paused', 'canceled'], MANDATE_STATUS_LABELS),
  },
  {
    key: 'kind',
    label: 'Type',
    kind: 'select',
    placeholder: 'Any type',
    options: optionsFor(['renewal', 'both', 'contribution'], MANDATE_KIND_LABELS),
  },
  {
    key: 'search',
    label: 'Search',
    kind: 'search',
    placeholder: 'Name or email',
    hint: 'Search by name, email, or the saved payment method.',
  },
];

/**
 * The reconciliation report's filters.  The list page picks fixed dates; a subscription
 * picks a **Period** relative to the day it is sent instead, since fixed dates would send
 * the same rows every time, so it is offered the period alone.
 */
const RECONCILIATION_FILTERS: FilterField[] = [
  { key: 'from', label: 'From', kind: 'date', listOnly: true },
  { key: 'to', label: 'To', kind: 'date', listOnly: true },
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
  periodField(PERIOD_OPTIONS, 'Any date'),
];

/**
 * One **Year** control wherever the contributions are filtered.  The list page picks a
 * calendar year; a subscription picks the year relative to the day it is sent, since a
 * fixed year would send the same list every time.  Blank, either one is this year: the
 * server's own choice, worked out on the day the report is built.
 */
const CONTRIBUTION_FILTERS: FilterField[] = [
  {
    key: 'year',
    label: 'Year',
    kind: 'select',
    placeholder: 'This year',
    options: earlierYears(),
    listOnly: true,
  },
  {
    ...periodField(
      PERIOD_OPTIONS.filter((option) => option.value === 'last_year'),
      'This year',
    ),
    label: 'Year',
  },
];

const DONOR_FILTERS: FilterField[] = [
  { key: 'from', label: 'From', kind: 'date' },
  { key: 'to', label: 'To', kind: 'date' },
  { key: 'search', label: 'Search', kind: 'search', placeholder: 'Name or email' },
  // Several counties at once, as the member list's own county filter takes them.
  {
    key: 'county',
    label: 'County',
    kind: 'multiselect',
    options: COUNTY_OPTIONS,
    hint: 'Check as many counties as you like.',
  },
  // The DARTs are the server's, so the page supplies them through `options`.
  { key: 'dart', label: 'DART', kind: 'select', placeholder: 'Any DART' },
  { key: 'min_cents', label: 'At least', kind: 'number', isDollars: true },
  { key: 'max_cents', label: 'At most', kind: 'number', isDollars: true },
  periodField(PERIOD_OPTIONS, 'Any date'),
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
      { value: 'bounced', label: 'Bounced' },
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
  roles: {
    slug: 'roles',
    label: 'Roles',
    filters: ROLE_FILTERS,
    choosable: true,
    periods: false,
  },
  verification: {
    slug: 'verification',
    label: 'Verification',
    filters: VERIFICATION_FILTERS,
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
  renewals: {
    slug: 'renewals',
    label: 'Renewals',
    filters: RENEWAL_FILTERS,
    choosable: true,
    periods: false,
  },
  reconciliation: {
    slug: 'reconciliation',
    label: 'Reconciliation',
    filters: RECONCILIATION_FILTERS,
    choosable: false,
    periods: true,
  },
  contributions: {
    slug: 'contributions',
    label: 'Contributions',
    filters: CONTRIBUTION_FILTERS,
    choosable: false,
    periods: true,
  },
  donors: {
    slug: 'donors',
    label: 'Donors',
    filters: DONOR_FILTERS,
    choosable: true,
    periods: true,
  },
  emails: {
    slug: 'emails',
    label: 'Sent emails',
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

/**
 * The fields the form that subscribes somebody to a report draws: every one but those
 * only its list page offers.
 *
 * @param definition the report being subscribed to.
 * @returns its filter fields in order, less the list-only ones.
 */
export function subscriptionFilters(definition: ReportDefinition): FilterField[] {
  return definition.filters.filter((field) => field.listOnly !== true);
}
