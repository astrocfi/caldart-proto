/**
 * The backups panel of `/portal/system` (PLAN §6.9): what is on disk, a button
 * that takes a fresh dump, and a download link per file.
 */
import type { Backup } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/DataTable';
import { DateText } from '../../components/DateText';
import { useToast } from '../../components/Toast';
import { backupDownloadUrl, useBackups, useCreateBackup } from './api';

/** Human file size; dumps run from a few hundred kB to a few hundred MB. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} kB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

const COLUMNS: Column<Backup>[] = [
  {
    key: 'name',
    header: 'File',
    render: (row) => <span className="mono">{row.name}</span>,
    sortValue: (row) => row.name,
  },
  {
    key: 'created_at',
    header: 'Taken',
    render: (row) => <DateText value={row.created_at} withTime />,
    sortValue: (row) => row.created_at,
  },
  {
    key: 'size_bytes',
    header: 'Size',
    numeric: true,
    render: (row) => <span className="mono">{formatBytes(row.size_bytes)}</span>,
    sortValue: (row) => row.size_bytes,
  },
  {
    key: 'download',
    header: 'Download',
    render: (row) => (
      <a
        className="button button--quiet button--small"
        href={backupDownloadUrl(row.name)}
        download={row.name}
      >
        Download
      </a>
    ),
  },
];

export function BackupsPanel() {
  const { data, isPending, isError, error } = useBackups();
  const create = useCreateBackup();
  const toast = useToast();

  const takeBackup = () => {
    create.mutate(undefined, {
      onSuccess: (backup) => toast.show(`Wrote ${backup.name}`, 'success'),
      onError: (failure) =>
        toast.show(failure instanceof Error ? failure.message : 'The backup failed.', 'error'),
    });
  };

  return (
    <Card
      eyebrow="Data"
      title="Backups"
      footer={
        <>
          <Button onClick={takeBackup} disabled={create.isPending}>
            {create.isPending ? 'Taking a backup…' : 'Create backup'}
          </Button>
          {create.isPending ? (
            <span className="muted" role="status">
              pg_dump is running; large databases take a minute.
            </span>
          ) : null}
        </>
      }
    >
      <p className="muted">
        Dumps are written to <code className="mono">BACKUP_DIR</code> on the server. Restoring one
        is a command-line job: <code className="mono">manage.py db_restore</code>.
      </p>

      {isError ? (
        <p className="field__error" role="alert">
          {error instanceof Error ? error.message : 'Could not list the backups.'}
        </p>
      ) : null}

      <DataTable
        columns={COLUMNS}
        rows={data ?? []}
        rowKey={(row) => row.name}
        isLoading={isPending}
        initialSort={{ key: 'created_at', direction: 'desc' }}
        emptyTitle="No backups yet"
        emptyDescription="Take one before the next upgrade or data import."
      />
    </Card>
  );
}
