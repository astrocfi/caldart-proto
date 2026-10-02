/**
 * One sent bulk email's results: the subject and date, the counts, a link to
 * the list as a CSV, and every person's result with its reason.
 */
import type { JSX } from 'react';

import type { BulkEmailDetail } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { recipientsCsvUrl } from './api';
import { peopleCaption, resultActions, resultLabel, sentSummary } from './results';

interface BulkEmailResultsProps {
  sent: BulkEmailDetail;
}

/** A send's heading, counts, download, and per-person table. */
export function BulkEmailResults({ sent }: BulkEmailResultsProps): JSX.Element {
  return (
    <section className="stack-tight" aria-label={`Results of ${sent.subject}`}>
      <RunActionsTable
        actions={resultActions(sent)}
        dryRun={false}
        heading="What became of each copy"
        kindLabel={resultLabel}
        detailHeader="Reason"
        hasWhenAndAmount={false}
        caption={peopleCaption(sent.recipients.length)}
        summary={
          <>
            <p>
              <strong>{sent.subject}</strong>
              <span className="muted"> · {formatDate(sent.created_at)}</span>
            </p>
            <p role="status">{sentSummary(sent)}</p>
            <p>
              <a href={recipientsCsvUrl(sent.id)} download>
                Download the list
              </a>
            </p>
          </>
        }
      />
    </section>
  );
}
