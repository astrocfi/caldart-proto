/**
 * Queries, mutations and pure arithmetic for the finance area.
 *
 * Every list query is keyed on the parameters it sends, so changing a filter
 * is a new query rather than a refetch of the same one, and every write
 * invalidates the whole `admin-payments` tree: a refund changes the row, the
 * summary and the member's ledger at once.
 *
 * The overview tiles deliberately ignore the filter bar: "this month" means
 * this month whatever the table below is showing.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type { ApiError } from '@/portal/api/client';
import type {
  DonorRow,
  FinanceMember,
  ManualPaymentPayload,
  MemberLedger,
  Paginated,
  Payment,
  PaymentDetail,
  PaymentPatch,
  PaymentPeriodSummary,
  PaymentProvider,
  RefundIssued,
  RefundRequest,
} from '@/portal/api/types';
import type { FilterValues } from '@/portal/reports/types';

export const FINANCE_KEY = ['admin-payments'] as const;

export type SummaryGroup = 'month' | 'year';

/**
 * Filters as query parameters, dropping everything left blank.
 *
 * @param filters the values a `FilterBar` holds, by query parameter.
 * @returns only the parameters that are set.
 */
export function filterParams(filters: FilterValues): Record<string, string> {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''));
}

/** Turns filter parameters into a URL query string, or `''` when there are none. */
export function queryString(params: Record<string, string>): string {
  const search = new URLSearchParams(params).toString();
  return search ? `?${search}` : '';
}

/** The href of one payment's receipt PDF. */
export function receiptUrl(paymentId: number): string {
  return `${API_BASE}/admin/payments/${paymentId}/receipt.pdf`;
}

/** The href of one member's contribution statement for `year`. */
export function statementUrl(userId: number, year: number): string {
  return `${API_BASE}/admin/payments/ledger/${userId}/statements/${year}.pdf`;
}

export interface ListOptions {
  page: number;
  pageSize: number;
  /** An `ordering` value the API accepts, e.g. `-paid_at`. */
  ordering: string;
}

/** The paginated payment list for the Payments tab, filtered, sorted and paged. */
export function useAdminPayments(
  filters: FilterValues,
  options: ListOptions,
): UseQueryResult<Paginated<Payment>> {
  const params = {
    ...filterParams(filters),
    ordering: options.ordering,
    page: String(options.page),
    page_size: String(options.pageSize),
  };
  return useQuery({
    queryKey: [...FINANCE_KEY, 'list', params],
    queryFn: () => api.get<Paginated<Payment>>(`/admin/payments${queryString(params)}`),
    placeholderData: keepPreviousData,
  });
}

/** The payment summary grouped by month or year, honoring the filter bar. */
export function useAdminPaymentSummary(
  group: SummaryGroup,
  filters: FilterValues,
): UseQueryResult<PaymentPeriodSummary[]> {
  const params = { ...filterParams(filters), group };
  return useQuery({
    queryKey: [...FINANCE_KEY, 'summary', params],
    queryFn: () => api.get<PaymentPeriodSummary[]>(`/admin/payments/summary${queryString(params)}`),
  });
}

/** Unfiltered monthly summary, which the overview tiles are computed from. */
export function useMonthlyTotals(): UseQueryResult<PaymentPeriodSummary[]> {
  return useQuery({
    queryKey: [...FINANCE_KEY, 'summary', { group: 'month' }],
    queryFn: () => api.get<PaymentPeriodSummary[]>('/admin/payments/summary?group=month'),
  });
}

/** One payment with its refunds, or disabled while `id` is not a number. */
export function usePaymentDetail(id: number | null): UseQueryResult<PaymentDetail> {
  return useQuery({
    queryKey: [...FINANCE_KEY, 'detail', id],
    queryFn: () => api.get<PaymentDetail>(`/admin/payments/${id}`),
    enabled: id !== null && Number.isFinite(id),
  });
}

/** One member's whole money history, or disabled while `userId` is not a number. */
export function useMemberLedger(userId: number | null): UseQueryResult<MemberLedger> {
  return useQuery({
    queryKey: [...FINANCE_KEY, 'ledger', userId],
    queryFn: () => api.get<MemberLedger>(`/admin/payments/ledger/${userId}`),
    enabled: userId !== null && Number.isFinite(userId),
  });
}

/**
 * Members whose name or address carries `term`, for the record form's search.
 *
 * The query only runs once something has been typed, because the endpoint
 * answers an empty list for a blank term anyway.
 */
export function useFinanceMemberSearch(term: string): UseQueryResult<FinanceMember[]> {
  return useQuery({
    queryKey: [...FINANCE_KEY, 'members', term],
    queryFn: () =>
      api.get<FinanceMember[]>(`/admin/payments/members?search=${encodeURIComponent(term)}`),
    enabled: term.length > 0,
  });
}

/**
 * The Donors tab's rows, via `GET /admin/payments/donors`, filtered.
 *
 * @param filters the donors report's filter values; blank ones are not sent.
 */
export function useDonors(filters: FilterValues): UseQueryResult<DonorRow[]> {
  const params = filterParams(filters);
  return useQuery({
    queryKey: [...FINANCE_KEY, 'donors', params],
    queryFn: () => api.get<DonorRow[]>(`/admin/payments/donors${queryString(params)}`),
    placeholderData: keepPreviousData,
  });
}

function useInvalidateFinance(): () => Promise<void> {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: FINANCE_KEY });
}

/** Reconciles a payment or writes its note; invalidates the finance tree on success. */
export function usePatchPayment(id: number): UseMutationResult<PaymentDetail, Error, PaymentPatch> {
  const invalidate = useInvalidateFinance();
  return useMutation({
    mutationFn: (payload: PaymentPatch) =>
      api.patch<PaymentDetail>(`/admin/payments/${id}`, payload),
    onSuccess: () => invalidate(),
  });
}

/** Issues a refund against a payment; invalidates the finance tree on success. */
export function useIssueRefund(id: number): UseMutationResult<RefundIssued, Error, RefundRequest> {
  const invalidate = useInvalidateFinance();
  return useMutation({
    mutationFn: (payload: RefundRequest) =>
      api.post<RefundIssued>(`/admin/payments/${id}/refunds`, payload),
    onSuccess: () => invalidate(),
  });
}

/** Emails the receipt again; invalidates the finance tree so the stamp redraws. */
export function useResendReceipt(id: number): UseMutationResult<unknown, Error, void> {
  const invalidate = useInvalidateFinance();
  return useMutation({
    mutationFn: () => api.post<unknown>(`/admin/payments/${id}/receipt`),
    onSuccess: () => invalidate(),
  });
}

/** Asks the provider again what a payment cost; invalidates the finance tree. */
export function useFetchFees(id: number): UseMutationResult<PaymentDetail, Error, void> {
  const invalidate = useInvalidateFinance();
  return useMutation({
    mutationFn: () => api.post<PaymentDetail>(`/admin/payments/${id}/fees`),
    onSuccess: () => invalidate(),
  });
}

/** Records money taken by check, cash or transfer; invalidates the finance tree. */
export function useRecordPayment(): UseMutationResult<PaymentDetail, Error, ManualPaymentPayload> {
  const invalidate = useInvalidateFinance();
  return useMutation({
    mutationFn: (payload: ManualPaymentPayload) =>
      api.post<PaymentDetail>('/admin/payments/record', payload),
    onSuccess: () => invalidate(),
  });
}

// --------------------------------------------------------------- tile math
/** One period's money, as the overview tiles report it. */
export interface Totals {
  count: number;
  grossCents: number;
  feeCents: number;
  netCents: number;
  refundedCents: number;
}

export const NO_TOTAL: Totals = {
  count: 0,
  grossCents: 0,
  feeCents: 0,
  netCents: 0,
  refundedCents: 0,
};

function add(totals: Totals, row: PaymentPeriodSummary): Totals {
  return {
    count: totals.count + row.count,
    grossCents: totals.grossCents + row.total_cents,
    feeCents: totals.feeCents + row.fee_cents,
    netCents: totals.netCents + row.net_cents,
    refundedCents: totals.refundedCents + row.refunded_cents,
  };
}

/** `2026-03` for a date, matching the server's month period labels. */
export function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

/** The `count` months ending with `today`, newest last. */
export function recentMonthKeys(count: number, today: Date): string[] {
  const keys: string[] = [];
  for (let back = count - 1; back >= 0; back -= 1) {
    keys.push(monthKey(new Date(today.getFullYear(), today.getMonth() - back, 1)));
  }
  return keys;
}

export interface DashboardTotals {
  thisMonth: Totals;
  yearToDate: Totals;
  lastTwelveMonths: Totals;
}

/** The three headline periods, from the unfiltered monthly summary. */
export function dashboardTotals(
  rows: PaymentPeriodSummary[],
  today: Date = new Date(),
): DashboardTotals {
  const thisMonthKey = monthKey(today);
  const yearPrefix = `${today.getFullYear()}-`;
  const window = new Set(recentMonthKeys(12, today));

  let thisMonth = NO_TOTAL;
  let yearToDate = NO_TOTAL;
  let lastTwelveMonths = NO_TOTAL;

  for (const row of rows) {
    if (row.period === thisMonthKey) thisMonth = add(thisMonth, row);
    if (row.period.startsWith(yearPrefix)) yearToDate = add(yearToDate, row);
    if (window.has(row.period)) lastTwelveMonths = add(lastTwelveMonths, row);
  }

  return { thisMonth, yearToDate, lastTwelveMonths };
}

/** Providers that actually appear in a summary, in a stable order. */
export function providersIn(rows: PaymentPeriodSummary[]): PaymentProvider[] {
  const order: PaymentProvider[] = ['stripe', 'paypal', 'mock', 'manual'];
  const seen = new Set<string>();
  for (const row of rows) {
    for (const provider of Object.keys(row.by_provider)) seen.add(provider);
  }
  return order.filter((provider) => seen.has(provider));
}

/**
 * The messages a failed write should show, keyed by field.
 *
 * `ApiError.fieldErrors` skips `detail`, so an error that carries nothing else —
 * a 404 for a member deleted since the search, a 403, any DRF error with only a
 * sentence — would leave the form silent.  Fall back to the sentence itself.
 */
export function reportedErrors(error: ApiError): Record<string, string> {
  const fields = error.fieldErrors;
  return Object.keys(fields).length > 0 ? fields : { detail: error.message };
}

/** What is left of a payment to refund, in cents: never below zero. */
export function unrefundedCents(payment: Pick<Payment, 'amount_cents' | 'refunded_cents'>): number {
  return Math.max(0, payment.amount_cents - payment.refunded_cents);
}
