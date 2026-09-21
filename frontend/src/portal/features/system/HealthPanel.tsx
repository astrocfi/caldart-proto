/**
 * The health panel of `/portal/system`.
 *
 * `healthChecks` turns the raw payload into one row per check with an ok /
 * warn / bad verdict; the component only renders what it returns.
 */
import type { JSX } from 'react';

import type { Health } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { formatDateTime } from '../../components/DateText';
import { StatusChip } from '../../components/StatusChip';
import type { StatusTone } from '../../components/StatusChip';
import { useHealth } from './api';

export type CheckVerdict = 'ok' | 'warn' | 'bad';

export interface HealthCheck {
  key: string;
  label: string;
  value: string;
  verdict: CheckVerdict;
  note?: string;
}

/** Free space below which a backup might not fit any more. */
export const DISK_WARN_MB = 2048;
export const DISK_BAD_MB = 512;

/** A backup older than this is stale; older than the second, negligent. */
export const BACKUP_WARN_DAYS = 7;
export const BACKUP_BAD_DAYS = 30;

const VERDICT_TONE: Record<CheckVerdict, StatusTone> = {
  ok: 'current',
  warn: 'expiring',
  bad: 'expired',
};

const VERDICT_LABEL: Record<CheckVerdict, string> = {
  ok: 'OK',
  warn: 'Warning',
  bad: 'Attention',
};

function daysSince(iso: string, now: Date): number {
  return (now.getTime() - new Date(iso).getTime()) / 86_400_000;
}

function backupCheck(health: Health, now: Date): HealthCheck {
  if (!health.last_backup) {
    return {
      key: 'last_backup',
      label: 'Last backup',
      value: 'never',
      verdict: 'bad',
      note: 'No dump has been taken on this machine.',
    };
  }
  const age = daysSince(health.last_backup, now);
  const verdict: CheckVerdict =
    age <= BACKUP_WARN_DAYS ? 'ok' : age <= BACKUP_BAD_DAYS ? 'warn' : 'bad';
  return {
    key: 'last_backup',
    label: 'Last backup',
    value: formatDateTime(health.last_backup),
    verdict,
    note: verdict === 'ok' ? undefined : `${Math.floor(age)} days ago.`,
  };
}

function diskCheck(health: Health): HealthCheck {
  const free = health.disk_free_mb;
  const verdict: CheckVerdict = free >= DISK_WARN_MB ? 'ok' : free >= DISK_BAD_MB ? 'warn' : 'bad';
  return {
    key: 'disk_free_mb',
    label: 'Disk free',
    value: `${free.toLocaleString('en-US')} MB`,
    verdict,
    note: verdict === 'ok' ? undefined : 'On the filesystem holding BACKUP_DIR.',
  };
}

/** Turn a health payload into the rows the panel renders. */
export function healthChecks(health: Health, now: Date = new Date()): HealthCheck[] {
  return [
    {
      key: 'db',
      label: 'Database',
      value: health.db,
      verdict: health.db === 'ok' ? 'ok' : 'bad',
    },
    {
      key: 'pending_migrations',
      label: 'Pending migrations',
      value: String(health.pending_migrations),
      verdict: health.pending_migrations === 0 ? 'ok' : 'warn',
      note: health.pending_migrations === 0 ? undefined : 'Run manage.py migrate.',
    },
    diskCheck(health),
    backupCheck(health, now),
    {
      key: 'version',
      label: 'Version',
      value: health.version,
      verdict: 'ok',
    },
    {
      key: 'debug',
      label: 'Debug mode',
      value: health.debug ? 'on' : 'off',
      verdict: health.debug ? 'bad' : 'ok',
      note: health.debug ? 'DEBUG must be off in production.' : undefined,
    },
  ];
}

/** Renders the server's health checks, with a button to refresh them. */
export function HealthPanel(): JSX.Element {
  const { data, isPending, isError, error, refetch, isFetching } = useHealth();

  return (
    <Card
      eyebrow="System"
      title="Health"
      footer={
        <Button variant="quiet" small onClick={() => void refetch()} disabled={isFetching}>
          {isFetching ? 'Checking…' : 'Refresh'}
        </Button>
      }
    >
      {isPending ? (
        <p className="muted" role="status">
          Checking…
        </p>
      ) : null}

      {isError ? (
        <p className="field__error" role="alert">
          {error instanceof Error ? error.message : 'Could not read the health report.'}
        </p>
      ) : null}

      {data ? (
        <div className="table-wrap">
          <table>
            <caption className="visually-hidden">System health checks</caption>
            <thead>
              <tr>
                <th scope="col">Check</th>
                <th scope="col">Value</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {healthChecks(data).map((check) => (
                <tr key={check.key}>
                  <th scope="row">{check.label}</th>
                  <td>
                    <span className="mono">{check.value}</span>
                    {check.note ? <div className="muted">{check.note}</div> : null}
                  </td>
                  <td>
                    <StatusChip
                      tone={VERDICT_TONE[check.verdict]}
                      label={VERDICT_LABEL[check.verdict]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Card>
  );
}
