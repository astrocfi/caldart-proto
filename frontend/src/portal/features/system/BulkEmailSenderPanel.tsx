/**
 * The bulk email sender panel of `/portal/system/scheduled`: run the sender by hand
 * and see which copies it sent.
 *
 * The sender runs every minute on its own. Each run starts every bulk email whose
 * start time has come and sends it, paced to the mail provider's limit, so a run by
 * hand matters only where no timer is running, such as on a developer's machine.
 * There is no dry run: the sender only ever sends what CalDART management has
 * already pressed Send on.
 */
import type { JSX } from 'react';

import type { BulkEmailRunResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useRunBulkEmailSender } from './api';

/** What the panel says when another run was already sending. */
export const SENDER_BUSY =
  'The sender is already running, so this run did nothing. Try again in a minute.';

/** The sentence shown after a run. */
export function senderRunSummary(result: BulkEmailRunResult): string {
  const { emails, sent, failed, skipped } = result;
  const worked = emails === 1 ? '1 bulk email' : `${emails} bulk emails`;
  return `Worked on ${worked}: sent ${sent}, failed ${failed}, and skipped ${skipped}.`;
}

/** What each kind of action reads as in the actions table. */
const KIND_LABELS: Record<string, string> = { sent: 'Sent', failed: 'Failed' };

function senderKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

/** Runs the bulk email sender on demand and reports what it sent. */
export function BulkEmailSenderPanel(): JSX.Element {
  const run = useRunBulkEmailSender();

  return (
    <Card
      eyebrow="Email"
      title="Bulk email sender"
      footer={
        <Button onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? 'Running…' : 'Run now'}
        </Button>
      }
    >
      <p className="muted">
        Every minute the server starts each bulk email whose time has come and sends its copies a
        few at a time, so the mail provider never turns them away. Run it here to send at once. A
        large send takes a while, and the page waits for it.
      </p>

      {run.isSuccess && run.data.busy ? <p role="status">{SENDER_BUSY}</p> : null}

      {run.isSuccess && !run.data.busy ? (
        <RunActionsTable
          actions={run.data.actions}
          dryRun={false}
          kindLabel={senderKindLabel}
          detailHeader="Subject or reason"
          hasWhenAndAmount={false}
          emptyTitle="Nothing was due"
          emptyDescription="No bulk email was waiting to send."
          summary={<p role="status">{senderRunSummary(run.data)}</p>}
        />
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The bulk email sender failed.'}
        </p>
      ) : null}
    </Card>
  );
}
