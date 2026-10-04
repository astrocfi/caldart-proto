/**
 * The **Reply-To** field of the compose screen's **What it says** card: the
 * address a reader's reply goes to. Every bulk email comes from the site's own
 * address, which nobody reads, so without this a reply reaches nobody.
 *
 * Empty, it stands for the sender's default address, which the hint names; nothing
 * is written in the box itself, so it never looks filled in. It saves itself on its
 * own, when the field is left or Enter is pressed, never together with the subject and
 * the message: a half-typed address must not stop the words from saving. An address
 * the server refuses is named under the field and the last good one stays saved.
 */
import { useState } from 'react';
import type { JSX, KeyboardEvent } from 'react';

import { ApiError } from '@/portal/api/client';
import { Field } from '@/portal/components/Field';
import { useUpdateBulkEmail } from './api';

/** The longest address the server accepts. */
const REPLY_TO_MAX_LENGTH = 254;

/** What the field says when the save fails without a reason of its own. */
const FALLBACK_ERROR = "The address for replies wasn't saved. Try again in a moment.";

interface ReplyToFieldProps {
  emailId: number;
  /** The address as saved; blank stands for `defaultReplyTo`. */
  saved: string;
  /** Where replies go when the field is empty. */
  defaultReplyTo: string;
}

/**
 * The hint under the field: what it is for, and what an empty field means.
 *
 * @param defaultReplyTo where replies go when the field is empty, blank for nowhere.
 */
export function replyToHint(defaultReplyTo: string): string {
  const purpose = 'When someone replies to this email, the reply goes to this address.';
  return defaultReplyTo === '' ? purpose : `${purpose} Leave it empty to use ${defaultReplyTo}.`;
}

/** Why the server refused the address, in words. */
function refusal(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_ERROR;
  return error.fieldErrors.reply_to ?? error.message;
}

/** The Reply-To address, saved when it is left, with a hint saying what it does. */
export function ReplyToField({ emailId, saved, defaultReplyTo }: ReplyToFieldProps): JSX.Element {
  const [value, setValue] = useState(saved);
  const [lastSaved, setLastSaved] = useState(saved);
  const update = useUpdateBulkEmail(emailId);
  const isSaved = update.isSuccess && value.trim() === lastSaved;

  const handleSave = (): void => {
    const next = value.trim();
    if (next === lastSaved) {
      update.reset();
      return;
    }
    update.mutate({ reply_to: next }, { onSuccess: (email) => setLastSaved(email.reply_to) });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSave();
    }
  };

  return (
    <div className="stack-tight">
      <Field
        label="Replies go to"
        error={update.isError ? refusal(update.error) : null}
        hint={replyToHint(defaultReplyTo)}
      >
        {(field) => (
          <input
            {...field}
            type="email"
            autoComplete="off"
            maxLength={REPLY_TO_MAX_LENGTH}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onBlur={handleSave}
            onKeyDown={handleKeyDown}
          />
        )}
      </Field>
      {isSaved ? (
        <p className="muted bulk-email__save-note" role="status">
          Address for replies saved.
        </p>
      ) : null}
    </div>
  );
}
