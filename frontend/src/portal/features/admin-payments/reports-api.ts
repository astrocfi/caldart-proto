/**
 * Queries, export hrefs and vocabulary for the finance area's three report
 * tabs: Reconciliation, Contributions and Renewals.
 *
 * The everyday list and its summary live in `./api`; these are the screens a
 * treasurer opens at the end of a month or a year, plus the standing renewal
 * authorities they administer, and they share nothing but the feature they sit
 * in.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type {
  ContributionRow,
  MandateStatus,
  Paginated,
  PaymentProvider,
  ReconciliationRow,
  RenewalAttempt,
  RenewalMandate,
  RenewalOutcome,
} from '@/portal/api/types';
import type { StatusTone } from '@/portal/components/StatusChip';
import { queryString } from './api';
import { PROVIDER_LABELS } from './labels';
import { periodLabel } from './PeriodTable';

/** How the reconciliation table gathers its rows. */
export type ReconciliationGroup = 'month' | 'year' | 'provider';

/** The groupings the segmented control offers, in the order it draws them. */
export const RECONCILIATION_GROUPS: readonly ReconciliationGroup[] = [
  'month',
  'year',
  'provider',
] as const;

/** The date range and provider a reconciliation run covers. */
export interface ReconciliationFilterState {
  from: string;
  to: string;
  provider: PaymentProvider | '';
}

export const EMPTY_RECONCILIATION_FILTERS: ReconciliationFilterState = {
  from: '',
  to: '',
  provider: '',
};

/** The query parameters for a reconciliation call, dropping everything blank. */
export function reconciliationParams(
  filters: ReconciliationFilterState,
  group: ReconciliationGroup,
): Record<string, string> {
  const params: Record<string, string> = { group };
  if (filters.from !== '') params.from = filters.from;
  if (filters.to !== '') params.to = filters.to;
  if (filters.provider !== '') params.provider = filters.provider;
  return params;
}

/** The reconciliation table, via `GET /admin/payments/reconciliation`. */
export function useReconciliation(
  filters: ReconciliationFilterState,
  group: ReconciliationGroup,
): UseQueryResult<ReconciliationRow[]> {
  const params = reconciliationParams(filters, group);
  return useQuery({
    queryKey: ['admin', 'payments', 'reconciliation', params],
    queryFn: () =>
      api.get<ReconciliationRow[]>(`/admin/payments/reconciliation${queryString(params)}`),
    placeholderData: (previous) => previous,
  });
}

/** The href behind an "Export CSV" or "Export PDF" button on Reconciliation. */
export function reconciliationExportUrl(
  filters: ReconciliationFilterState,
  group: ReconciliationGroup,
  format: 'csv' | 'pdf',
): string {
  const query = queryString(reconciliationParams(filters, group));
  return `${API_BASE}/admin/payments/reconciliation/export.${format}${query}`;
}

/** The year-end giving list, via `GET /admin/payments/contributions`. */
export function useContributions(year: number): UseQueryResult<ContributionRow[]> {
  return useQuery({
    queryKey: ['admin', 'payments', 'contributions', year],
    queryFn: () => api.get<ContributionRow[]>(`/admin/payments/contributions?year=${year}`),
    placeholderData: (previous) => previous,
  });
}

/** The href behind an export button on Contributions. */
export function contributionsExportUrl(year: number, format: 'csv' | 'pdf'): string {
  return `${API_BASE}/admin/payments/contributions/export.${format}?year=${year}`;
}

/** One member's contribution statement for one year, as a PDF download. */
export function statementUrl(userId: number, year: number): string {
  return `${API_BASE}/admin/payments/ledger/${userId}/statements/${year}.pdf`;
}

/** How many mandates and attempts one page of the Renewals tab holds. */
export const RENEWAL_PAGE_SIZE = 50;

/** The standing renewal authorities, via `GET /admin/renewals`, one page at a time. */
export function useRenewalMandates(
  status: MandateStatus | '',
  search: string,
  page: number,
): UseQueryResult<Paginated<RenewalMandate>> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(RENEWAL_PAGE_SIZE),
  };
  if (status !== '') params.status = status;
  if (search !== '') params.search = search;
  return useQuery({
    queryKey: ['admin', 'renewals', 'mandates', params],
    queryFn: () => api.get<Paginated<RenewalMandate>>(`/admin/renewals${queryString(params)}`),
    placeholderData: (previous) => previous,
  });
}

/** The scheduled charges, via `GET /admin/renewals/attempts`, one page at a time. */
export function useRenewalAttempts(
  outcome: RenewalOutcome | '',
  page: number,
): UseQueryResult<Paginated<RenewalAttempt>> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(RENEWAL_PAGE_SIZE),
  };
  if (outcome !== '') params.outcome = outcome;
  return useQuery({
    queryKey: ['admin', 'renewals', 'attempts', params],
    queryFn: () =>
      api.get<Paginated<RenewalAttempt>>(`/admin/renewals/attempts${queryString(params)}`),
    placeholderData: (previous) => previous,
  });
}

/**
 * Turn a member's automatic renewal off on their behalf, via
 * `DELETE /admin/renewals/{id}`.
 *
 * The mandate is canceled rather than deleted and the member is emailed, so
 * both lists on the tab are refetched once the call returns.
 */
export function useCancelMandate(): UseMutationResult<void, unknown, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mandateId: number) => api.delete<void>(`/admin/renewals/${mandateId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'renewals'] });
    },
  });
}

/* ------------------------------------------------------------- vocabulary */
export const MANDATE_STATUS_LABELS: Record<MandateStatus, string> = {
  pending: 'Awaiting a method',
  active: 'On',
  paused: 'Paused',
  canceled: 'Off',
};

export const MANDATE_STATUS_TONES: Record<MandateStatus, StatusTone> = {
  pending: 'new',
  active: 'current',
  paused: 'expiring',
  canceled: 'none',
};

export const RENEWAL_OUTCOME_LABELS: Record<RenewalOutcome, string> = {
  scheduled: 'Scheduled',
  succeeded: 'Charged',
  failed: 'Refused',
  skipped: 'Skipped',
};

export const RENEWAL_OUTCOME_TONES: Record<RenewalOutcome, StatusTone> = {
  scheduled: 'new',
  succeeded: 'current',
  failed: 'expired',
  skipped: 'none',
};

/** `2026-03` reads as `March 2026`; a year reads as itself, a provider by its name. */
export function reconciliationPeriodLabel(period: string, group: ReconciliationGroup): string {
  if (group === 'provider') {
    const label: string | undefined = PROVIDER_LABELS[period as PaymentProvider];
    return label ?? period;
  }
  return periodLabel(period, group);
}
