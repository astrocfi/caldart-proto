/**
 * The portal's one client for the report endpoints under `/api/v1/reports/`.
 *
 * Every report is read the same way: `GET /reports` lists those the caller may
 * read, `GET /reports/<slug>/columns` is a report's column registry, and
 * `/reports/<slug>/export.csv` and `export.pdf` are its downloads.  Every
 * export button in the portal takes its href from `reportExportUrl`.  The
 * signed-in user's own named sets of a report's columns live under
 * `/reports/<slug>/column-sets`.
 *
 * The reports sent by email are read and changed here too: the subscriptions
 * under `/reports/subscriptions` and the DART rosters under `/reports/rosters`.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type {
  ReportColumn,
  ReportRunResult,
  ReportSubscription,
  ReportSubscriptionCreate,
  ReportSubscriptionPatch,
  ReportSummary,
  Roster,
  SavedColumnSet,
  SavedColumnSetWrite,
} from '@/portal/api/types';
import type { ReportFormat, ReportSlug } from './types';

export const REPORTS_KEY = ['reports'] as const;
export const SUBSCRIPTIONS_KEY = ['reports', 'subscriptions'] as const;
export const ROSTERS_KEY = ['reports', 'rosters'] as const;

/** A report's parameters: a value, a list of values such as the columns, or nothing. */
export type ReportParams = Readonly<Record<string, string | readonly string[] | undefined>>;

/** The list page's own parameter, which no report takes: a report carries every row. */
const PAGE_PARAM = 'page';

/**
 * The href of one report's download, carrying every parameter that is set.
 *
 * An empty or absent value is left out, as is `page`; a list, such as the
 * chosen `columns`, is sent comma-separated and left out when it is empty.
 *
 * @param slug the report, as the server's registry names it.
 * @param format `csv` or `pdf`, which is also the extension of the file.
 * @param params the filters, `ordering`, `columns` and `period` to send.
 * @returns a same-origin path such as `/api/v1/reports/members/export.pdf?dart=3`.
 */
export function reportExportUrl(
  slug: ReportSlug,
  format: ReportFormat,
  params: ReportParams,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === PAGE_PARAM || value === undefined) continue;
    const text = typeof value === 'string' ? value : value.join(',');
    if (text !== '') query.set(key, text);
  }
  const search = query.toString();
  const base = `${API_BASE}/reports/${slug}/export.${format}`;
  return search === '' ? base : `${base}?${search}`;
}

/** The reports the signed-in user may read, via `GET /reports`; a member has none. */
export function useReports(): UseQueryResult<ReportSummary[]> {
  return useQuery({
    queryKey: REPORTS_KEY,
    queryFn: () => api.get<ReportSummary[]>('/reports'),
  });
}

/**
 * Every column one report can carry, in export order, via `GET /reports/<slug>/columns`.
 *
 * A registry never changes while the portal is open, so it is fetched once and kept.
 */
export function useReportColumns(slug: ReportSlug): UseQueryResult<ReportColumn[]> {
  return useQuery({
    queryKey: [...REPORTS_KEY, slug, 'columns'],
    queryFn: () => api.get<ReportColumn[]>(`/reports/${slug}/columns`),
    staleTime: Infinity,
  });
}

/** Every subscription for a report the caller may read, via `GET /reports/subscriptions`. */
export function useSubscriptions(): UseQueryResult<ReportSubscription[]> {
  return useQuery({
    queryKey: SUBSCRIPTIONS_KEY,
    queryFn: () => api.get<ReportSubscription[]>('/reports/subscriptions'),
  });
}

/**
 * Sets up a subscription via `POST /reports/subscriptions`.
 *
 * A refusal is an `ApiError` whose body is keyed by field: `recipient_email`
 * for an account that may not read the report, `confirmed` for an address no
 * account holds, and `filters` holding the report's own errors by filter.
 */
export function useCreateSubscription(): UseMutationResult<
  ReportSubscription,
  unknown,
  ReportSubscriptionCreate
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportSubscriptionCreate) =>
      api.post<ReportSubscription>('/reports/subscriptions', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SUBSCRIPTIONS_KEY });
    },
  });
}

/** One subscription and the fields to change on it. */
export interface SubscriptionEdit {
  id: number;
  patch: ReportSubscriptionPatch;
}

/** Changes a subscription, such as pausing or resuming it, via `PATCH /reports/subscriptions/{id}`. */
export function useUpdateSubscription(): UseMutationResult<
  ReportSubscription,
  unknown,
  SubscriptionEdit
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: SubscriptionEdit) =>
      api.patch<ReportSubscription>(`/reports/subscriptions/${id}`, patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SUBSCRIPTIONS_KEY });
    },
  });
}

/** Deletes a subscription via `DELETE /reports/subscriptions/{id}`. */
export function useDeleteSubscription(): UseMutationResult<void, unknown, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/reports/subscriptions/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SUBSCRIPTIONS_KEY });
    },
  });
}

/**
 * Sends one subscription at once, whatever its date, via
 * `POST /reports/subscriptions/{id}/send`.
 *
 * Its next date stays where it is; its last-sent time, and whether a recipient
 * who lost the role has been paused, change, so the list is read again.
 */
export function useSendSubscription(): UseMutationResult<ReportRunResult, unknown, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<ReportRunResult>(`/reports/subscriptions/${id}/send`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SUBSCRIPTIONS_KEY });
    },
  });
}

/** Every active DART's roster: who receives it and when it last went, via `GET /reports/rosters`. */
export function useRosters(): UseQueryResult<Roster[]> {
  return useQuery({
    queryKey: ROSTERS_KEY,
    queryFn: () => api.get<Roster[]>('/reports/rosters'),
  });
}

/**
 * Sends every DART's roster now, or rehearses it, via `POST /reports/rosters/send`.
 *
 * A dry run changes nothing, so only a real one reads the rosters again.
 */
export function useSendRosters(): UseMutationResult<ReportRunResult, unknown, boolean> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dryRun: boolean) =>
      api.post<ReportRunResult>('/reports/rosters/send', { dry_run: dryRun }),
    onSuccess: (_result, dryRun) => {
      if (dryRun) return;
      void queryClient.invalidateQueries({ queryKey: ROSTERS_KEY });
    },
  });
}

/** The query key of the signed-in user's saved column sets for one report. */
function columnSetsKey(slug: ReportSlug) {
  return [...REPORTS_KEY, slug, 'column-sets'] as const;
}

/**
 * The signed-in user's own saved sets of one report's columns, by name, via
 * `GET /reports/<slug>/column-sets`.
 *
 * @param slug the report whose sets to read.
 */
export function useColumnSets(slug: ReportSlug): UseQueryResult<SavedColumnSet[]> {
  return useQuery({
    queryKey: columnSetsKey(slug),
    queryFn: () => api.get<SavedColumnSet[]>(`/reports/${slug}/column-sets`),
  });
}

/**
 * Save a named set of one report's columns via `POST /reports/<slug>/column-sets`.
 *
 * Saving under a name the user already has replaces that set's columns and keeps
 * its id.  The saved set goes straight into the cached list, so a drop-down can
 * select it at once, and the list is then read again for the server's order.
 */
export function useSaveColumnSet(
  slug: ReportSlug,
): UseMutationResult<SavedColumnSet, Error, SavedColumnSetWrite> {
  const queryClient = useQueryClient();
  const key = columnSetsKey(slug);
  return useMutation({
    mutationFn: (payload: SavedColumnSetWrite) =>
      api.post<SavedColumnSet>(`/reports/${slug}/column-sets`, payload),
    onSuccess: async (saved) => {
      queryClient.setQueryData<SavedColumnSet[]>(key, (sets = []) => [
        ...sets.filter((set) => set.id !== saved.id),
        saved,
      ]);
      await queryClient.invalidateQueries({ queryKey: key });
    },
  });
}

/**
 * Delete one of the user's saved column sets, by id, via
 * `DELETE /reports/<slug>/column-sets/<id>`; the set leaves the cached list at once.
 */
export function useDeleteColumnSet(slug: ReportSlug): UseMutationResult<null, Error, number> {
  const queryClient = useQueryClient();
  const key = columnSetsKey(slug);
  return useMutation({
    mutationFn: (id: number) => api.delete<null>(`/reports/${slug}/column-sets/${id}`),
    onSuccess: async (_nothing, id) => {
      queryClient.setQueryData<SavedColumnSet[]>(key, (sets = []) =>
        sets.filter((set) => set.id !== id),
      );
      await queryClient.invalidateQueries({ queryKey: key });
    },
  });
}
