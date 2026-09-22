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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type {
  Backup,
  Health,
  Paginated,
  ReminderKind,
  ReminderLogEntry,
  ReminderRunResult,
} from '@/portal/api/types';

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
      if (!dryRun) void queryClient.invalidateQueries({ queryKey: ['system', 'reminders', 'log'] });
    },
  });
}

/** Plain href so the browser downloads through the session cookie. */
export function backupDownloadUrl(name: string): string {
  return `${API_BASE}/system/backups/${encodeURIComponent(name)}/download`;
}
