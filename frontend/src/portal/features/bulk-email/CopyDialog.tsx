/**
 * One person's copy of a sent bulk email, exactly as it went: the subject and the
 * email in a sandboxed frame, filled in with the details stored when it was sent.
 *
 * It opens under the delivery report's table as a dialog that does not cover the
 * page. The focus moves to its **Close** button; **Close**, and the Escape key while the
 * focus is inside the dialog, shut it, and the caller puts the focus back on the button
 * that opened it. Links in the copy open in a new tab.
 */
import { useEffect, useId, useRef } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { Button } from '@/portal/components/Button';
import { DateText } from '@/portal/components/DateText';
import { EmailFrame } from '@/portal/components/EmailFrame';
import { useRecipientCopy } from './deliveryApi';
import './delivery.css';
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
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, [rowId]);

  // The Escape key closes the dialog while the focus is inside it, and only then, so a
  // key pressed elsewhere on the page is left to whatever has the focus there.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return undefined;
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      handleClose();
    };
    dialog.addEventListener('keydown', handleKeyDown);
    return () => dialog.removeEventListener('keydown', handleKeyDown);
  }, [handleClose]);

  return (
    <dialog
      ref={dialogRef}
      open
      className="bulk-email__copy stack-tight"
      aria-labelledby={headingId}
    >
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
          <EmailFrame title={`The email as ${name} received it`} html={copy.data.html} />
        </>
      )}
    </dialog>
  );
}
