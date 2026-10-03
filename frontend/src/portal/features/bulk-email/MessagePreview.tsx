/**
 * The preview at the top of **Check and send**: the email as one person in the
 * batch will receive it, their details filled in, with **Previous** and **Next**
 * to step through everybody who receives a copy.
 *
 * The email is drawn in a sandboxed frame, so nothing in it can run or reach the
 * portal. The preview shows the saved message, and is read again each time the
 * message or the batch is saved.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail, BulkEmailPreview } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { useBulkEmailPreview } from './richTextApi';
import './preview.css';

/** What the preview says when it cannot be shown and the server gave no reason. */
const FALLBACK_ERROR = 'The preview could not be shown. Try again in a moment.';

/**
 * Whose copy the preview shows, in words: `Previewing as Ann Able (1 of 38)`, or
 * the sender's own copy while nobody in the batch receives one.
 */
export function previewingLine(preview: BulkEmailPreview): string {
  if (preview.recipient.id === null) {
    return `Previewing as you, ${preview.recipient.name}: nobody in the batch receives it yet.`;
  }
  return `Previewing as ${preview.recipient.name} (${preview.position} of ${preview.count})`;
}

/** The reason the server refused the preview, in words. */
function refusal(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_ERROR;
  const fields = error.fieldErrors;
  return fields.body ?? fields.subject ?? fields.recipient_id ?? error.message;
}

/** The preview of `email`'s saved message, one person at a time. */
export function MessagePreview({ email }: { email: BulkEmailDetail }): JSX.Element {
  const [recipientId, setRecipientId] = useState<number | null>(null);
  const version = `${email.updated_at}/${email.receiving_count}`;
  const preview = useBulkEmailPreview(email.id, recipientId, version);

  if (preview.isError) {
    return (
      <section className="bulk-email__preview stack-tight" aria-label="Preview">
        <p className="field__error" role="alert">
          {`The preview cannot be shown: ${refusal(preview.error)}`}
        </p>
      </section>
    );
  }
  if (preview.data === undefined) {
    return (
      <section className="bulk-email__preview" aria-label="Preview">
        <p className="muted">Loading the preview…</p>
      </section>
    );
  }
  const shown = preview.data;
  const previousId = shown.previous_id;
  const nextId = shown.next_id;

  return (
    <section className="bulk-email__preview stack-tight" aria-label="Preview">
      <div className="cluster bulk-email__preview-bar">
        <p role="status">{previewingLine(shown)}</p>
        <div className="cluster">
          <Button
            small
            variant="quiet"
            disabled={previousId === null}
            onClick={() => setRecipientId(previousId)}
          >
            Previous person
          </Button>
          <Button
            small
            variant="quiet"
            disabled={nextId === null}
            onClick={() => setRecipientId(nextId)}
          >
            Next person
          </Button>
        </div>
      </div>
      <p>
        <strong>Subject:</strong> {shown.subject}
      </p>
      <iframe
        className="bulk-email__preview-frame"
        title={`The email as ${shown.recipient.name} will receive it`}
        sandbox=""
        srcDoc={shown.html}
      />
    </section>
  );
}
