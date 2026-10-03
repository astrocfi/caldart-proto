/**
 * One person's copy of a sent bulk email, exactly as it went: the subject and the
 * email in a sandboxed frame, filled in with the details stored when it was sent.
 *
 * It opens under the delivery report's table as a dialog that does not cover the
 * page. The focus moves to its **Close** button; **Close** and the Escape key shut it,
 * and the caller puts the focus back on the button that opened it.
 */
import { useEffect, useId, useRef } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { Button } from '@/portal/components/Button';
import { DateText } from '@/portal/components/DateText';
import { useRecipientCopy } from './deliveryApi';
import './delivery.css';
import './preview.css';
import { resultLabel } from './status';

/** What the dialog says when the copy cannot be shown and the server gave no reason. */
const FALLBACK_ERROR = 'This copy could not be shown. Try again in a moment.';

export interface CopyDialogProps {
  /** The email. */
  emailId: number;
  /** The person's row in the batch, and their name, for the heading. */
  rowId: number;
  name: string;
  /** Shuts the dialog. */
  onClose: () => void;
}

/** The copy sent to one person, in a dialog under the table. */
export function CopyDialog({
  emailId,
  rowId,
  name,
  onClose: handleClose,
}: CopyDialogProps): JSX.Element {
  const copy = useRecipientCopy(emailId, rowId);
  const headingId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, [rowId]);

  // The Escape key closes the dialog from anywhere on the page while it is open.
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleClose]);

  return (
    <dialog open className="bulk-email__copy stack-tight" aria-labelledby={headingId}>
      <div className="cluster bulk-email__copy-bar">
        <h3 id={headingId}>{`The copy sent to ${name}`}</h3>
        <Button ref={closeRef} small variant="secondary" onClick={handleClose}>
          Close
        </Button>
      </div>
      {copy.isError ? (
        <p className="field__error" role="alert">
          {copy.error instanceof ApiError ? copy.error.message : FALLBACK_ERROR}
        </p>
      ) : copy.data === undefined ? (
        <p className="muted">Loading the copy…</p>
      ) : (
        <>
          <p className="muted">
            {resultLabel(copy.data.status)} to {copy.data.email} on{' '}
            <DateText value={copy.data.tried_at} withTime />. This is the copy exactly as it went,
            with the details it was sent with.
          </p>
          <p>
            <strong>Subject:</strong> {copy.data.subject}
          </p>
          <iframe
            className="bulk-email__preview-frame"
            title={`The email as ${name} received it`}
            sandbox=""
            srcDoc={copy.data.html}
          />
        </>
      )}
    </dialog>
  );
}
