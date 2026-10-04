/**
 * Card 2 of the compose screen, **What it says**: the type, the subject, the
 * Reply-To address, and the message, with **Send me a test** at the bottom. The
 * type saves the moment it is chosen (`EmailTypeChoice`).
 *
 * Both save themselves as they are typed; a quiet note under the message says
 * whether the latest words are saved. The compose screen owns the values and the
 * saving, so Send can make sure the last words are saved before it goes. The
 * message is written in the rich text editor, and **Insert field** puts a
 * recipient's detail, such as their first name, into the subject or the message.
 * **Start from a template** and **Save as a template** sit at the top
 * (`TemplateControls`).
 */
import { useId, useRef } from 'react';
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { RichTextEditor } from '@/portal/components/RichTextEditor';
import type { RichTextEditorHandle } from '@/portal/components/RichTextEditor';
import { EmailTypeChoice } from './EmailTypeChoice';
import { InsertFieldMenu } from './InsertFieldMenu';
import { ReplyToField } from './ReplyToField';
import { uploadBulkEmailImage } from './richTextApi';
import { TemplateControls } from './StartFromTemplate';
import { TestSendButton } from './TestSendButton';
import type { SaveState } from './useAutosave';

/** The longest subject the server accepts. */
const SUBJECT_MAX_LENGTH = 200;

/** What the note under the message says for each save state. */
const SAVE_NOTES: Record<SaveState, string> = {
  idle: '',
  saved: 'Saved',
  saving: 'Saving…',
  failed: 'Not saved yet. Your words are kept here, and saving tries again as you type.',
};

/** What the message's hint says while it can be written. */
const MESSAGE_HINT =
  'Use the buttons for bold, headings, lists, links, and pictures. Insert field puts in ' +
  "each person's own details, such as their first name.";

interface MessageCardProps {
  emailId: number;
  /** The chosen type's id, or null while none is chosen. */
  emailType: number | null;
  emailTypeName: string;
  subject: string;
  body: string;
  /** The Reply-To address as saved, blank for `defaultReplyTo`; it saves itself. */
  replyTo: string;
  defaultReplyTo: string;
  onSubjectChange: (subject: string) => void;
  onBodyChange: (body: string) => void;
  /** Save what is typed before a test goes; resolves true once it is saved. */
  onBeforeTest: () => Promise<boolean>;
  saveState: SaveState;
  /** The server's complaint about each field, if it refused one. */
  errors: { subject?: string; body?: string };
  /** False once the email has started sending: the fields are then shown, not changed. */
  isEditable: boolean;
  /** Save the words on the screen; resolves true once they are saved. */
  onBeforeReplace: () => Promise<boolean>;
  /** Called once a template's words are saved in the email, to show them. */
  onReplaced: () => void;
}

/** The subject and message fields, with the save note. */
export function MessageCard({
  emailId,
  emailType,
  emailTypeName,
  subject,
  body,
  replyTo,
  defaultReplyTo,
  onSubjectChange: handleSubjectChange,
  onBodyChange: handleBodyChange,
  onBeforeTest: handleBeforeTest,
  saveState,
  errors,
  isEditable,
  onBeforeReplace: handleBeforeReplace,
  onReplaced: handleReplaced,
}: MessageCardProps): JSX.Element {
  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<RichTextEditorHandle>(null);
  const messageId = useId();
  const hintId = `${messageId}-hint`;
  const errorId = `${messageId}-error`;
  const describedBy = [errors.body === undefined ? null : errorId, isEditable ? hintId : null]
    .filter((id) => id !== null)
    .join(' ');

  return (
    <Card title="2. What it says" className="bulk-email__card">
      {isEditable ? (
        <p className="muted">
          Choose the type, then write the subject and the message. Everything saves itself as you
          type, so you can leave and come back later.
        </p>
      ) : null}
      {isEditable ? (
        <TemplateControls
          emailId={emailId}
          subject={subject}
          body={body}
          emailType={emailType}
          replyTo={replyTo}
          onBeforeReplace={handleBeforeReplace}
          onReplaced={handleReplaced}
        />
      ) : null}
      <EmailTypeChoice
        emailId={emailId}
        emailType={emailType}
        emailTypeName={emailTypeName}
        isEditable={isEditable}
      />
      <fieldset className="bulk-email__fieldset stack" disabled={!isEditable}>
        <legend className="visually-hidden">The message</legend>
        <Field label="Subject" error={errors.subject} hint="One line that says what it is about.">
          {(field) => (
            <input
              {...field}
              ref={subjectRef}
              type="text"
              maxLength={SUBJECT_MAX_LENGTH}
              value={subject}
              onChange={(event) => handleSubjectChange(event.target.value)}
            />
          )}
        </Field>
        <ReplyToField emailId={emailId} saved={replyTo} defaultReplyTo={defaultReplyTo} />
        <div className="field">
          {/* The editing area names itself "Message"; this is the label a reader sees. */}
          <span className="field__label" aria-hidden="true">
            Message
          </span>
          <RichTextEditor
            ref={editorRef}
            label="Message"
            value={body}
            onChange={handleBodyChange}
            onUploadImage={(file) => uploadBulkEmailImage(file)}
            describedBy={describedBy === '' ? undefined : describedBy}
            invalid={errors.body !== undefined}
            readOnly={!isEditable}
            toolbarExtra={
              isEditable ? (
                <InsertFieldMenu
                  subjectRef={subjectRef}
                  onSubjectChange={handleSubjectChange}
                  editorRef={editorRef}
                />
              ) : null
            }
          />
          {errors.body === undefined ? null : (
            <span className="field__error" id={errorId} role="alert">
              {errors.body}
            </span>
          )}
          {isEditable ? (
            <span className="field__hint" id={hintId}>
              {MESSAGE_HINT}
            </span>
          ) : null}
        </div>
      </fieldset>
      {isEditable && saveState !== 'idle' ? (
        <p
          className={saveState === 'failed' ? 'field__error' : 'muted bulk-email__save-note'}
          role="status"
        >
          {SAVE_NOTES[saveState]}
        </p>
      ) : null}
      {isEditable ? <TestSendButton emailId={emailId} onBeforeSend={handleBeforeTest} /> : null}
    </Card>
  );
}
