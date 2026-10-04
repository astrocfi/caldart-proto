/**
 * The preview at the top of **Check and send**: the email as one person in the
 * batch will receive it, their details filled in, with **Previous** and **Next**
 * to step through everybody who receives a copy.
 *
 * The email is drawn in the shared `EmailFrame`, as the archive and the delivery
 * report draw it: nothing in it can run or reach the portal, and its links open in a
 * new tab. The preview shows the saved message, and is read again each time the
 * message or the batch is saved. A change to the batch starts it again from the
 * first person, since the person shown may have left it, and so does the server
 * saying the person shown is no longer in the batch. Before the message is written
 * it says the preview appears once it is, and while the words typed could not be
 * saved it says it shows the last saved version.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail, BulkEmailPreview } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { EmailFrame } from '@/portal/components/EmailFrame';
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

/** The person whose copy is shown, null for the first, and the batch they came from. */
interface Choice {
  batch: string;
  id: number | null;
}

/** Whether `error` is the server saying the person asked for is not in the batch. */
function isNotInBatch(error: unknown): boolean {
  return error instanceof ApiError && error.fieldErrors.recipient_id !== undefined;
}

/** What the preview says before the message is written. */
export const NO_MESSAGE_YET = 'The preview appears once you write the message.';

/** What the preview says while the words on the screen could not be saved. */
export const LAST_SAVED_NOTE =
  'This preview shows the last saved version. Your latest changes are not in it yet.';

interface MessagePreviewProps {
  email: BulkEmailDetail;
  /** True while the words on the screen could not be saved, so the preview is behind. */
  isBehind?: boolean;
}

/** The preview of `email`'s saved message, one person at a time. */
export function MessagePreview({ email, isBehind = false }: MessagePreviewProps): JSX.Element {
  if (email.body.trim() === '') {
    return (
      <section className="bulk-email__preview" aria-label="Preview">
        <p className="muted">{NO_MESSAGE_YET}</p>
      </section>
    );
  }
  return <PersonPreview email={email} isBehind={isBehind} />;
}

/** The preview of a written message, with the person shown and the steps between people. */
function PersonPreview({ email, isBehind }: Required<MessagePreviewProps>): JSX.Element {
  // The person chosen, remembered with the batch they were chosen from: once the
  // batch changes, the choice no longer stands and the first person is shown.
  const batchVersion = `${email.batch_count}/${email.receiving_count}`;
  const [choice, setChoice] = useState<Choice>({ batch: batchVersion, id: null });
  const recipientId = choice.batch === batchVersion ? choice.id : null;
  const preview = useBulkEmailPreview(email.id, recipientId, `${email.updated_at}/${batchVersion}`);
  const isPersonGone = recipientId !== null && isNotInBatch(preview.error);

  useEffect(() => {
    if (isPersonGone) setChoice({ batch: batchVersion, id: null });
  }, [isPersonGone, batchVersion]);

  if (preview.isError && !isPersonGone) {
    return (
      <section className="bulk-email__preview stack-tight" aria-label="Preview">
        <p className="field__error" role="alert">
          {`The preview cannot be shown: ${refusal(preview.error)}`}
        </p>
      </section>
    );
  }
  if (preview.data === undefined || isPersonGone) {
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
            onClick={() => setChoice({ batch: batchVersion, id: previousId })}
          >
            Previous person
          </Button>
          <Button
            small
            variant="quiet"
            disabled={nextId === null}
            onClick={() => setChoice({ batch: batchVersion, id: nextId })}
          >
            Next person
          </Button>
        </div>
      </div>
      {isBehind ? <p className="field__error">{LAST_SAVED_NOTE}</p> : null}
      <p>
        <strong>Subject:</strong> {shown.subject}
      </p>
      <EmailFrame
        title={`The email as ${shown.recipient.name} will receive it`}
        html={shown.html}
      />
    </section>
  );
}
