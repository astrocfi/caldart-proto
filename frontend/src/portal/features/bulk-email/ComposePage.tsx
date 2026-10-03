/**
 * `/bulk-email/compose/:id`: the compose screen of one bulk email.
 *
 * It reads top to bottom as three numbered cards: **Who gets it** (the batch),
 * **What it says** (the subject and the message), and **Check and send**. The
 * draft saves itself as it is typed. Once Send is pressed, a banner at the top
 * says where the email stands, with the one action that fits: the countdown or
 * the scheduled time with **Cancel**, the progress with **Stop sending**, or the
 * result. A scheduled email can still be changed; once an email has started
 * sending the screen holds still, without the drafting instructions, and the
 * Check and send card is gone. The email is read again every few seconds while it
 * waits to start or is sending.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { BulkEmailDetail } from '@/portal/api/types';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { useBulkEmail } from './api';
import './bulk-email.css';
import { MessageCard } from './MessageCard';
import { RecipientsCard } from './RecipientsCard';
import { SendCard } from './SendCard';
import { SendStatus } from './SendStatus';
import { useAutosave } from './useAutosave';

/** The compose screen of the email named in the address. */
export function ComposePage(): JSX.Element {
  const id = Number(useParams().id);
  const email = useBulkEmail(id);
  // Moved on when a template replaces the words, so the form starts again from them.
  const [generation, setGeneration] = useState(0);

  if (email.isError) {
    return (
      <Page title="Compose" eyebrow="Bulk Email">
        <p className="field__error" role="alert">
          This email could not be loaded. It may have been deleted.{' '}
          <Link to="/bulk-email/drafts">See your drafts</Link>.
        </p>
      </Page>
    );
  }
  if (email.data === undefined) return <Loading />;
  // Keyed by the email, so the fields start from this email's words.
  return (
    <ComposeForm
      key={`${email.data.id}-${generation}`}
      email={email.data}
      onReplaced={() => setGeneration((count) => count + 1)}
    />
  );
}

/** The banner and the three cards, for an email already read. */
function ComposeForm({
  email,
  onReplaced: handleReplaced,
}: {
  email: BulkEmailDetail;
  /** Called once a template's words are saved in the email. */
  onReplaced: () => void;
}): JSX.Element {
  const {
    values,
    setSubject: handleSubjectChange,
    setBody: handleBodyChange,
    flush: handleBeforeSend,
    saveState,
    errors,
  } = useAutosave(email, email.can_edit);
  const isSendable = email.status === 'draft' || (email.can_edit && email.status === 'queued');

  return (
    <Page
      title={email.status === 'draft' ? 'Compose' : 'Bulk email'}
      eyebrow="Bulk Email"
      lede={
        email.can_edit
          ? 'Choose who gets it, write it, then check and send. Your work saves itself.'
          : undefined
      }
    >
      {email.not_sent_reason === '' ? null : (
        <p className="bulk-email__notice" role="status">
          {email.not_sent_reason}
        </p>
      )}
      <Banner email={email} />
      <RecipientsCard
        emailId={email.id}
        isEditable={email.can_edit}
        isQueued={email.status === 'queued'}
      />
      <MessageCard
        emailId={email.id}
        emailType={email.email_type}
        emailTypeName={email.email_type_name}
        subject={values.subject}
        body={values.body}
        onSubjectChange={handleSubjectChange}
        onBodyChange={handleBodyChange}
        saveState={saveState}
        errors={errors}
        isEditable={email.can_edit}
        onBeforeReplace={handleBeforeSend}
        onReplaced={handleReplaced}
      />
      {isSendable ? (
        <SendCard
          email={email}
          subject={values.subject}
          body={values.body}
          onBeforeSend={handleBeforeSend}
        />
      ) : null}
    </Page>
  );
}

/** What each state of the banner is called, for a reader moving by landmarks. */
const BANNER_NAMES: Partial<Record<BulkEmailDetail['status'], string>> = {
  queued: 'Waiting to send',
  sending: 'Sending',
  sent: 'Sent',
  stopped: 'Stopped',
};

/** The banner over the cards: where the email stands once Send has been pressed. */
function Banner({ email }: { email: BulkEmailDetail }): JSX.Element | null {
  const name = BANNER_NAMES[email.status];
  if (name === undefined) return null;
  return (
    <section className="bulk-email__notice stack-tight" aria-label={name}>
      {email.can_edit ? null : (
        <p>
          {email.status === 'sent'
            ? 'This email has been sent, so it can no longer be changed.'
            : 'This email has started sending, so it can no longer be changed.'}{' '}
          {email.status === 'sent' || email.status === 'stopped' ? null : (
            <Link to={`/bulk-email/sent/${email.id}`}>See who received it</Link>
          )}
        </p>
      )}
      <SendStatus email={email} isDetailLinked />
    </section>
  );
}
