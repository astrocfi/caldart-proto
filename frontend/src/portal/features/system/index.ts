/** System administration screen (PLAN §8).  Owned by `feat/ops`. */

export { BackupsPanel, formatBytes } from './BackupsPanel';
export { HealthPanel, healthChecks } from './HealthPanel';
export type { CheckVerdict, HealthCheck } from './HealthPanel';
export { KIND_LABELS, RemindersPanel, runSummary } from './RemindersPanel';
export { SystemPage } from './SystemPage';
export {
  BACKUPS_KEY,
  HEALTH_KEY,
  backupDownloadUrl,
  reminderLogKey,
  useBackups,
  useCreateBackup,
  useHealth,
  useReminderLog,
  useRunReminders,
} from './api';
