/**
 * Card 2 of the compose screen, **What it says**: the subject and the message.
 *
 * Both save themselves as they are typed; a quiet note under the message says
 * whether the latest words are saved. The compose screen owns the values and the
 * saving, so Send can make sure the last words are saved before it goes.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import type { SaveState } from './useAutosave';

/** The longest subject the server accepts. */
const SUBJECT_MAX_LENGTH = 200;

/** The longest message the server accepts. */
const BODY_MAX_LENGTH = 20000;

/** What the note under the message says for each save state. */
const SAVE_NOTES: Record<SaveState, string> = {
  idle: '',
  saved: 'Saved',
  saving: 'Saving…',
  failed: 'Not saved yet. Your words are kept here, and saving tries again as you type.',
};

interface MessageCardProps {
  subject: string;
  body: string;
  onSubjectChange: (subject: string) => void;
  onBodyChange: (body: string) => void;
  saveState: SaveState;
  /** The server's complaint about each field, if it refused one. */
  errors: { subject?: string; body?: string };
  /** False once the email has started sending: the fields are then shown, not changed. */
  isEditable: boolean;
}

/** The subject and message fields, with the save note. */
export function MessageCard({
  subject,
  body,
  onSubjectChange: handleSubjectChange,
  onBodyChange: handleBodyChange,
  saveState,
  errors,
  isEditable,
}: MessageCardProps): JSX.Element {
  return (
    <Card title="2. What it says" className="bulk-email__card">
      {isEditable ? (
        <p className="muted">
          Write the subject and the message. Everything saves itself as you type, so you can leave
          and come back later.
        </p>
      ) : null}
      <fieldset className="bulk-email__fieldset stack" disabled={!isEditable}>
        <legend className="visually-hidden">The message</legend>
        <Field label="Subject" error={errors.subject} hint="One line that says what it is about.">
          {(field) => (
            <input
              {...field}
              type="text"
              maxLength={SUBJECT_MAX_LENGTH}
              value={subject}
              onChange={(event) => handleSubjectChange(event.target.value)}
            />
          )}
        </Field>
        <Field
          label="Message"
          error={errors.body}
          hint="Plain text. Leave a blank line between paragraphs."
        >
          {(field) => (
            <textarea
              {...field}
              rows={12}
              maxLength={BODY_MAX_LENGTH}
              value={body}
              onChange={(event) => handleBodyChange(event.target.value)}
            />
          )}
        </Field>
      </fieldset>
      {isEditable && saveState !== 'idle' ? (
        <p
          className={saveState === 'failed' ? 'field__error' : 'muted bulk-email__save-note'}
          role="status"
        >
          {SAVE_NOTES[saveState]}
        </p>
      ) : null}
    </Card>
  );
}
