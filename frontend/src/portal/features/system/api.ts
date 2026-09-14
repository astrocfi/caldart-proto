/**
 * Queries and mutations behind `/portal/system`.
 *
 * All four endpoints are `system_admin` only; the route guard keeps anyone
 * else from ever mounting these hooks.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '../../api/client';
import type {
  Backup,
  Health,
  Paginated,
  ReminderKind,
  ReminderLogEntry,
  ReminderRunResult,
} from '../../api/types';

export const HEALTH_KEY = ['system', 'health'] as const;
export const BACKUPS_KEY = ['system', 'backups'] as const;

/** Reminder log rows are cached per kind filter. */
export function reminderLogKey(kind: ReminderKind | 'all') {
  return ['system', 'reminders', 'log', kind] as const;
}

/** How many recent reminders the panel shows. */
export const REMINDER_LOG_PAGE_SIZE = 20;

export function useHealth(): UseQueryResult<Health> {
  return useQuery({
    queryKey: HEALTH_KEY,
    queryFn: () => api.get<Health>('/system/health'),
    staleTime: 15_000,
  });
}

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
