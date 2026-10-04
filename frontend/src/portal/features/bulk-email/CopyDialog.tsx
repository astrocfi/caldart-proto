/**
 * One person's copy of a sent bulk email, exactly as it went: the subject and the
 * email in a sandboxed frame, filled in with the details stored when it was sent.
 *
 * It opens as a dialog over the page, beside the row it belongs to whatever the
 * scroll, and the page behind it waits until it is shut. The focus moves to its
 * **Close** button; **Close** and the Escape key shut it, and the caller puts the focus
 * back on the button that opened it once the dialog has gone. Links in the copy open in a
 * new tab.
 */
import { useEffect, useId, useRef } from 'react';
import type { JSX, SyntheticEvent } from 'react';

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

/** The copy sent to one person, in a dialog over the page. */
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

  // Opened as a modal, so the page behind waits; a browser without modal dialogs
  // shows it open in place instead.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return undefined;
    if (typeof dialog.showModal === 'function') {
      if (!dialog.open) dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
    // Shut before it goes, so the page behind takes the focus again at once.
    return () => {
      if (dialog.open && typeof dialog.close === 'function') dialog.close();
    };
  }, []);

  useEffect(() => {
    closeRef.current?.focus();
  }, [rowId]);

  // The browser's own Escape would shut the dialog behind React's back; the dialog
  // closes through the caller instead, so the focus goes back to View copy.
  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>): void => {
    event.preventDefault();
    handleClose();
  };

  // The Escape key closes the dialog while the focus is inside it.
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
      className="bulk-email__copy stack-tight"
      aria-labelledby={headingId}
      aria-modal="true"
      onCancel={handleCancel}
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
