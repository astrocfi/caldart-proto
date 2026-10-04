/**
 * The health panel of `/portal/system/health`.
 *
 * `healthChecks` turns the raw payload into one row per check with an ok /
 * warn / bad verdict, each value and note in plain words: what is wrong and who to
 * ask, never a command or a setting's name.  The component only renders what it
 * returns.
 */
import type { JSX } from 'react';

import type { Health } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDateTime } from '@/portal/components/DateText';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
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
  ok: 'Good',
  warn: 'Warning',
  bad: 'Problem',
};

/** Who fixes anything on the server itself. */
const INSTALLER = 'the person who installed the site';

/** Days from `iso` to `now`, with the fraction of a day. */
function daysSince(iso: string, now: Date): number {
  return (now.getTime() - new Date(iso).getTime()) / 86_400_000;
}

/** The last backup's row: when it was taken, graded by its age. */
function backupCheck(health: Health, now: Date): HealthCheck {
  if (!health.last_backup) {
    return {
      key: 'last_backup',
      label: 'Last backup',
      value: 'No backup yet',
      verdict: 'bad',
      note: 'Take one under Backups below.',
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

/** Free space in GB with one decimal, or in whole MB below a gigabyte. */
function diskSpace(megabytes: number): string {
  if (megabytes < 1024) return `${megabytes.toLocaleString('en-US')} MB`;
  const gigabytes = megabytes / 1024;
  return `${gigabytes.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} GB`;
}

/** The free disk space's row, graded against the room a backup needs. */
function diskCheck(health: Health): HealthCheck {
  const free = health.disk_free_mb;
  const verdict: CheckVerdict = free >= DISK_WARN_MB ? 'ok' : free >= DISK_BAD_MB ? 'warn' : 'bad';
  return {
    key: 'disk_free_mb',
    label: 'Disk free',
    value: diskSpace(free),
    verdict,
    note: verdict === 'ok' ? undefined : 'On the disk that holds the backups.',
  };
}

/** The database upgrade's row: complete, or how many steps an upgrade left unapplied. */
function upgradeCheck(health: Health): HealthCheck {
  const waiting = health.pending_migrations;
  if (waiting === 0) {
    return {
      key: 'pending_migrations',
      label: 'Database upgrade',
      value: 'Complete',
      verdict: 'ok',
    };
  }
  return {
    key: 'pending_migrations',
    label: 'Database upgrade',
    // The server cannot count the steps while the database is down.
    value: waiting < 0 ? 'Unknown' : `${waiting} ${waiting === 1 ? 'step' : 'steps'} not applied`,
    verdict: 'warn',
    note:
      waiting < 0
        ? 'The database could not be reached to check.'
        : `An upgrade was left half finished. Tell ${INSTALLER}.`,
  };
}

/** Turn a health payload into the rows the panel renders. */
export function healthChecks(health: Health, now: Date = new Date()): HealthCheck[] {
  return [
    {
      key: 'db',
      label: 'Database',
      value: health.db === 'ok' ? 'Connected' : 'Not reachable',
      verdict: health.db === 'ok' ? 'ok' : 'bad',
      note:
        health.db === 'ok'
          ? undefined
          : `The site is down or about to be. Tell ${INSTALLER} at once.`,
    },
    upgradeCheck(health),
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
      value: health.debug ? 'On' : 'Off',
      verdict: health.debug ? 'bad' : 'ok',
      note: health.debug
        ? `It shows internal details to anyone who causes an error. Ask ${INSTALLER} to turn it off.`
        : undefined,
    },
  ];
}

/** Renders the server's health checks, with a button to refresh them. */
export function HealthPanel(): JSX.Element {
  const { data, isPending, isError, error, refetch, isFetching } = useHealth();

  return (
    <Card
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
                    <span className="num">{check.value}</span>
                    {check.note ? <div className="muted">{check.note}</div> : null}
                  </td>
                  <td>
                    <StatusDot
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
