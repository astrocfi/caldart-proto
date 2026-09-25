/**
 * Queries and mutations behind `/portal/system`, and the reminder log an
 * account administrator reads at `/admin/reminders`.
 *
 * `useReminderLog` is the one hook `account_admin` reaches: its endpoint,
 * `GET /admin/reminders/log`, is readable by account and system
 * administrators alike, and both screens mount it. Every other hook here
 * calls a `system_admin`-only endpoint, and the route guard on
 * `/portal/system` keeps anyone else from mounting it.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type {
  Backup,
  EmailLogEntry,
  EmailPurpose,
  Health,
  Paginated,
  ReminderKind,
  ReminderLogEntry,
  ReminderRunResult,
  RenewalRunResult,
  ReportRunResult,
} from '@/portal/api/types';
import { ROSTERS_KEY, SUBSCRIPTIONS_KEY } from '@/portal/reports/api';
import type { FilterValues } from '@/portal/reports/types';

export const HEALTH_KEY = ['system', 'health'] as const;
export const BACKUPS_KEY = ['system', 'backups'] as const;

/** Reminder log rows are cached per kind filter. */
export function reminderLogKey(
  kind: ReminderKind | 'all',
): readonly ['system', 'reminders', 'log', ReminderKind | 'all'] {
  return ['system', 'reminders', 'log', kind] as const;
}

/** How many recent reminders the panel shows. */
export const REMINDER_LOG_PAGE_SIZE = 20;

/** The server's health checks, via `GET /system/health`. */
export function useHealth(): UseQueryResult<Health> {
  return useQuery({
    queryKey: HEALTH_KEY,
    queryFn: () => api.get<Health>('/system/health'),
    staleTime: 15_000,
  });
}

/** The database dumps on disk, via `GET /system/backups`. */
export function useBackups(): UseQueryResult<Backup[]> {
  return useQuery({
    queryKey: BACKUPS_KEY,
    queryFn: () => api.get<Backup[]>('/system/backups'),
  });
}

/** Taking a dump also changes "last backup", so health is refreshed too. */
export function useCreateBackup(): UseMutationResult<Backup, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Backup>('/system/backups'),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: BACKUPS_KEY });
      void queryClient.invalidateQueries({ queryKey: HEALTH_KEY });
    },
  });
}

/** A page of the reminder log for `kind`, via `GET /admin/reminders/log`. */
export function useReminderLog(
  kind: ReminderKind | 'all',
): UseQueryResult<Paginated<ReminderLogEntry>> {
  return useQuery({
    queryKey: reminderLogKey(kind),
    queryFn: () =>
      api.get<Paginated<ReminderLogEntry>>('/admin/reminders/log', {
        query: {
          kind: kind === 'all' ? undefined : kind,
          page_size: REMINDER_LOG_PAGE_SIZE,
        },
      }),
  });
}

/** Runs the reminder scan (or a dry run) via `POST /system/reminders/run`. */
export function useRunReminders(): UseMutationResult<ReminderRunResult, unknown, boolean> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dryRun: boolean) =>
      api.post<ReminderRunResult>('/system/reminders/run', { dry_run: dryRun }),
    onSuccess: (_result, dryRun) => {
      // A dry run writes nothing, so there is no new log row to fetch.
      if (dryRun) return;
      void queryClient.invalidateQueries({ queryKey: ['system', 'reminders', 'log'] });
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
    },
  });
}

/**
 * Runs the automatic-renewal scan (or a rehearsal) via `POST /system/renewals/run`.
 *
 * A real run charges cards and activates terms, so the finance area's own
 * queries are dropped afterwards; a dry run writes nothing and leaves them be.
 */
export function useRunRenewals(): UseMutationResult<RenewalRunResult, unknown, boolean> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dryRun: boolean) =>
      api.post<RenewalRunResult>('/system/renewals/run', { dry_run: dryRun }),
    onSuccess: (_result, dryRun) => {
      if (dryRun) return;
      void queryClient.invalidateQueries({ queryKey: ['admin', 'renewals'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'payments'] });
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
    },
  });
}

/**
 * Runs the report sender (or a rehearsal) via `POST /system/reports/run`: every
 * subscription and DART roster that is due.
 *
 * A real run moves the subscriptions' dates and the rosters' last-sent times
 * and writes to the email log, so those are read again; a dry run changes
 * nothing.
 */
export function useRunScheduledReports(): UseMutationResult<ReportRunResult, unknown, boolean> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dryRun: boolean) =>
      api.post<ReportRunResult>('/system/reports/run', { dry_run: dryRun }),
    onSuccess: (_result, dryRun) => {
      if (dryRun) return;
      void queryClient.invalidateQueries({ queryKey: SUBSCRIPTIONS_KEY });
      void queryClient.invalidateQueries({ queryKey: ROSTERS_KEY });
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
    },
  });
}

/** Plain href so the browser downloads through the session cookie. */
export function backupDownloadUrl(name: string): string {
  return `${API_BASE}/system/backups/${encodeURIComponent(name)}/download`;
}

/**
 * How many emails one page of the log holds: the server's standard page, which
 * the panel leaves the server to choose and only uses to count the rows shown.
 */
export const EMAIL_LOG_PAGE_SIZE = 25;

/** The purposes the email log's filter offers are the server's, and never change. */
export const EMAIL_PURPOSES_KEY = ['system', 'emails', 'purposes'] as const;

/** What one page of the email log is asked for: the filters, the order and the page. */
export interface EmailLogQuery {
  /** `purpose`, `status`, `from`, `to` and `q`, an empty value meaning unset. */
  filters: FilterValues;
  /** The `ordering` term, such as `-sent_at`. */
  ordering: string;
  /** The page, from 1. */
  page: number;
}

/** Email log pages are cached per filter set, order and page. */
export function emailLogKey({
  filters,
  ordering,
  page,
}: EmailLogQuery): readonly ['system', 'emails', 'log', FilterValues, string, number] {
  return ['system', 'emails', 'log', filters, ordering, page] as const;
}

/**
 * One page of the emails the system has tried to send, via `GET /system/emails`.
 *
 * @param query the filters, the order and the page to ask for; an empty filter
 *   value is left out of the request.
 * @returns the page, with the total count and the links to its neighbors.
 */
export function useEmailLog(query: EmailLogQuery): UseQueryResult<Paginated<EmailLogEntry>> {
  const { filters, ordering, page } = query;
  return useQuery({
    queryKey: emailLogKey(query),
    queryFn: () =>
      api.get<Paginated<EmailLogEntry>>('/system/emails', {
        query: { ...filters, ordering, page: page > 1 ? page : undefined },
      }),
    placeholderData: keepPreviousData,
  });
}

/** The purposes the log's filter offers, as `{value, label}`, via `GET /system/emails/purposes`. */
export function useEmailPurposes(): UseQueryResult<EmailPurpose[]> {
  return useQuery({
    queryKey: EMAIL_PURPOSES_KEY,
    queryFn: () => api.get<EmailPurpose[]>('/system/emails/purposes'),
    staleTime: Infinity,
  });
}
