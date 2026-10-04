/**
 * The aircraft database panel of `/portal/system/health`: when the FAA registry's
 * aircraft types and the registrations the N-number box offers were last
 * imported, and **Run now** to import them again.
 *
 * There is no dry run: the import changes nothing but those two reference
 * tables.  The server starts the import in its own process and answers at once,
 * so the panel shows it running and asks for its state every few seconds until
 * it ends.
 */
import { useRef } from 'react';
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate, formatTime } from '@/portal/components/DateText';
import { useFocusAfterSave } from '@/portal/components/focus';
import { useRegistryStatus } from '@/portal/api/queries';
import type { RegistryStatus } from '@/portal/api/types';
import { useRunRegistryImport } from './api';

/** `count` and `noun`, the noun in the plural unless the count is one. */
function counted(count: number, noun: string): string {
  return `${count} ${count === 1 ? noun : `${noun}s`}`;
}

/**
 * The panel's status line: *Running since HH:MM* while an import runs, then
 * what the last import wrote and on which day (and the hand-added types it
 * folded into the FAA's, when any), or *Failed:* and its error.
 */
export function registryImportSummary({ running, last }: RegistryStatus): string {
  if (last === null) return 'No import has run yet.';
  if (running) {
    return `Running since ${formatTime(last.started_at)}`;
  }
  if (!last.ok) return `Failed: ${last.error}`;
  const written =
    `Imported ${counted(last.types_written, 'type')} and ` +
    `${counted(last.registrations_written, 'registration')} on ` +
    formatDate(last.finished_at);
  if (last.types_folded === 0) return `${written}.`;
  return `${written}, folded ${counted(last.types_folded, 'hand-added type')}.`;
}

/** Runs the FAA registry import on demand and follows it to its end. */
export function RegistryPanel(): JSX.Element {
  const status = useRegistryStatus();
  const run = useRunRegistryImport();
  // The button is disabled while it runs; it gets the focus back once the run ends.
  const runRef = useRef<HTMLButtonElement>(null);
  useFocusAfterSave(runRef, run.isPending);
  const isRunning = status.data?.running === true;

  const handleRun = (): void => {
    run.mutate();
  };

  return (
    <Card
      eyebrow="Aircraft"
      title="Aircraft database"
      footer={
        <Button ref={runRef} onClick={handleRun} disabled={isRunning || run.isPending}>
          {isRunning ? 'Running…' : 'Run now'}
        </Button>
      }
    >
      <p className="muted">
        Loads the FAA aircraft registry, which is what the N-number box on an aircraft form offers.
        It runs every night and changes nothing else, so running it again is harmless.
      </p>

      {status.data === undefined ? null : <p role="status">{registryImportSummary(status.data)}</p>}

      {status.isError ? (
        <p className="field__error" role="alert">
          The registry&rsquo;s state could not be loaded.
        </p>
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The import could not be started.'}
        </p>
      ) : null}
    </Card>
  );
}
