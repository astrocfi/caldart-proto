/**
 * `/bulk-email/drafts/:id`: the compose screen of one bulk email.
 *
 * It reads top to bottom as three numbered cards: **Who gets it** (the batch),
 * **What it says** (the subject and the message), and **Check and send**. The
 * draft saves itself as it is typed. A queued email opens here too, under a
 * banner with its countdown or scheduled time and **Cancel**, and can still be
 * changed; once it has started sending the screen holds still and says so, with
 * a link to its Sent page. The email is read again every few seconds while it
 * waits to start or is sending.
 */
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
import { QueuedStatus } from './SendStatus';
import { useAutosave } from './useAutosave';

/** The compose screen of the email named in the address. */
export function ComposePage(): JSX.Element {
  const id = Number(useParams().id);
  const email = useBulkEmail(id);

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
  return <ComposeForm key={email.data.id} email={email.data} />;
}

/** The three cards and the banner, for an email already read. */
function ComposeForm({ email }: { email: BulkEmailDetail }): JSX.Element {
  const {
    values,
    setSubject: handleSubjectChange,
    setBody: handleBodyChange,
    flush: handleBeforeSend,
    saveState,
    errors,
  } = useAutosave(email, email.can_edit);

  return (
    <Page
      title={email.status === 'draft' ? 'Compose' : 'Bulk email'}
      eyebrow="Bulk Email"
      lede="Choose who gets it, write it, then check and send. Your work saves itself."
    >
      <Notice email={email} />
      <RecipientsCard emailId={email.id} isEditable={email.can_edit} />
      <MessageCard
        subject={values.subject}
        body={values.body}
        onSubjectChange={handleSubjectChange}
        onBodyChange={handleBodyChange}
        saveState={saveState}
        errors={errors}
        isEditable={email.can_edit}
      />
      <SendCard
        email={email}
        subject={values.subject}
        body={values.body}
        onBeforeSend={handleBeforeSend}
      />
    </Page>
  );
}

/** The banner over the cards: a queued email's countdown, or a started one's notice. */
function Notice({ email }: { email: BulkEmailDetail }): JSX.Element | null {
  if (email.status === 'queued') {
    return (
      <section className="bulk-email__notice" aria-label="Waiting to send">
        <QueuedStatus email={email} />
      </section>
    );
  }
  if (email.can_edit) return null;
  return (
    <section className="bulk-email__notice" aria-label="Already sent">
      <p>
        {email.status === 'sending'
          ? 'This email is being sent, so it can no longer be changed.'
          : 'This email has been sent, so it can no longer be changed.'}{' '}
        <Link to={`/bulk-email/sent/${email.id}`}>See who received it</Link>.
      </p>
    </section>
  );
}
