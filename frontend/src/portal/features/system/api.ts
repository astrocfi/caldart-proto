/**
 * Queries and mutations behind the System pages under `/portal/system/`, and the reminder log and
 * schedule an account administrator reads at `/admin/reminders`.
 *
 * `useReminderLog` and `useReminderSchedule` are the hooks `account_admin` reaches: their
 * endpoints, `GET /admin/reminders/log` and `GET /admin/reminders/schedule`, are readable by
 * account and system administrators alike, and both screens mount them. Every other hook here
 * calls a `system_admin`-only endpoint, and the route guard on the System pages keeps anyone else
 * from mounting it.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import { ADMIN_USERS_KEY, REGISTRY_KEY } from '@/portal/api/queries';
import type {
  Backup,
  BounceRunResult,
  BounceStatus,
  BulkEmailRunResult,
  EmailLogEntry,
  EmailPurpose,
  Health,
  Paginated,
  ReminderKind,
  ReminderLogEntry,
  ReminderRunResult,
  ReminderSchedule,
  ReminderSchedulePayload,
  RenewalRunResult,
  ReportRunResult,
  RegistryImport,
  StatementsRunResult,
} from '@/portal/api/types';
import { MEMBERS_KEY } from '@/portal/features/admin-members/api';
import { ROSTERS_KEY, SUBSCRIPTIONS_KEY } from '@/portal/reports/api';
import type { FilterValues } from '@/portal/reports/types';
import { API_BASE } from '@/portal/urlPrefix';

export const HEALTH_KEY = ['system', 'health'] as const;
export const BACKUPS_KEY = ['system', 'backups'] as const;

/** Reminder log rows are cached per kind filter. */
export function reminderLogKey(
  kind: ReminderKind | 'all',
): readonly ['system', 'reminders', 'log', ReminderKind | 'all'] {
  return ['system', 'reminders', 'log', kind] as const;
}

/** The reminder schedule, read by both reminder screens. */
export const REMINDER_SCHEDULE_KEY = ['system', 'reminders', 'schedule'] as const;

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

/** When each reminder stage falls, via `GET /admin/reminders/schedule`. */
export function useReminderSchedule(): UseQueryResult<ReminderSchedule> {
  return useQuery({
    queryKey: REMINDER_SCHEDULE_KEY,
    queryFn: () => api.get<ReminderSchedule>('/admin/reminders/schedule'),
  });
}

/**
 * Saves the reminder schedule via `PUT /admin/reminders/schedule` (system administrators).
 *
 * The email log's purpose labels name the schedule's days, so they are read again too.
 */
export function useSaveReminderSchedule(): UseMutationResult<
  ReminderSchedule,
  Error,
  ReminderSchedulePayload
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReminderSchedulePayload) =>
      api.put<ReminderSchedule>('/admin/reminders/schedule', payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(REMINDER_SCHEDULE_KEY, saved);
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
    },
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

/** What a statements run is asked for: the year, and whether it is a rehearsal. */
export interface StatementsRunOptions {
  year: number;
  dryRun: boolean;
}

/**
 * Runs the year-end statement sender (or a rehearsal) via `POST /system/statements/run`.
 *
 * A real run writes `YearStatement` rows and sends mail, so the email log is
 * read again; a dry run changes nothing.
 */
export function useRunStatements(): UseMutationResult<
  StatementsRunResult,
  unknown,
  StatementsRunOptions
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ year, dryRun }: StatementsRunOptions) =>
      api.post<StatementsRunResult>('/system/statements/run', { year, dry_run: dryRun }),
    onSuccess: (_result, { dryRun }) => {
      if (dryRun) return;
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
    },
  });
}

/** Whether bounce checking is set up, via `GET /system/bounces`, read as the panel loads. */
export function useBounceStatus(): UseQueryResult<BounceStatus> {
  return useQuery({
    queryKey: ['system', 'bounces'],
    queryFn: () => api.get<BounceStatus>('/system/bounces'),
  });
}

/**
 * Runs the bounce check (or a rehearsal) via `POST /system/bounces/run`: reads the
 * bounce mailbox and marks every email that bounced.
 *
 * A real run changes email log rows and flags accounts, so the log and the user and
 * member records are read again; a dry run changes nothing.
 */
export function useRunBounces(): UseMutationResult<BounceRunResult, unknown, boolean> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dryRun: boolean) =>
      api.post<BounceRunResult>('/system/bounces/run', { dry_run: dryRun }),
    onSuccess: (_result, dryRun) => {
      if (dryRun) return;
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
      void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
      void queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}

/**
 * Runs the bulk email sender once via `POST /system/bulk-email/run`: every queued bulk
 * email whose start time has come is started and sent.
 *
 * A run changes the bulk emails and writes to the email log, so both are read again.
 */
export function useRunBulkEmailSender(): UseMutationResult<BulkEmailRunResult, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<BulkEmailRunResult>('/system/bulk-email/run'),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bulk-email'] });
      void queryClient.invalidateQueries({ queryKey: ['system', 'emails'] });
    },
  });
}

/**
 * Starts the FAA registry import via `POST /admin/system/registry-import`.  The
 * server answers at once with the import row, before the import finishes, so the
 * registry's state is read again and follows the import while it runs.  A second
 * press while one runs is refused with a 409.
 */
export function useRunRegistryImport(): UseMutationResult<RegistryImport, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<RegistryImport>('/admin/system/registry-import'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: REGISTRY_KEY }),
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

/**
 * The purposes the email log's filter offers are the server's. They change only when the
 * reminder schedule is saved, which drops them along with the rest of the email log.
 */
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

/** One email of the log, via `GET /system/emails/{id}`, for its page on Sent emails. */
export function useEmailLogEntry(id: number): UseQueryResult<EmailLogEntry> {
  return useQuery({
    queryKey: ['system', 'emails', 'entry', id],
    queryFn: () => api.get<EmailLogEntry>(`/system/emails/${id}`),
  });
}

interface UseEmailPurposesOptions {
  /**
   * Whether to fetch at all. Defaults to `true`; a caller that only needs the
   * purposes once some other condition holds (such as the emails report being
   * the one chosen) passes `false` until then, so the request is never sent to
   * a caller who cannot read it.
   */
  enabled?: boolean;
}

/** The purposes the log's filter offers, as `{value, label}`, via `GET /system/emails/purposes`. */
export function useEmailPurposes({ enabled = true }: UseEmailPurposesOptions = {}): UseQueryResult<
  EmailPurpose[]
> {
  return useQuery({
    queryKey: EMAIL_PURPOSES_KEY,
    queryFn: () => api.get<EmailPurpose[]>('/system/emails/purposes'),
    staleTime: Infinity,
    enabled,
  });
}
