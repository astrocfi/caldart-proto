/**
 * `/bulk-email/sent/:id`: one bulk email that has started sending.
 *
 * At the top are the subject, who sent it and when, and where it stands: the
 * progress with **Stop** while it sends, or the counts, with **Send the rest**
 * after a stop. Then the message as it was sent, in a sandboxed frame with its
 * recipient field tokens as written, with whether it is on the recipients' Messages
 * page, and the delivery report: every person in the batch with what became of their
 * copy and why. A mission callout links to its answers. The page is read again every
 * few seconds while the email is sending.
 */
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { BulkEmailDetail } from '@/portal/api/types';
import { useMe } from '@/portal/auth/useAuth';
import { Card } from '@/portal/components/Card';
import { formatDateAt } from '@/portal/components/DateText';
import { EmailFrame } from '@/portal/components/EmailFrame';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { useBulkEmail, useBulkSender } from './api';
import './bulk-email.css';
import { DeliveryReport } from './DeliveryReport';
import { MessagesVisibility } from './MessagesVisibility';
import { DuplicateButton } from './DuplicateButton';
import { SendStatus } from './SendStatus';

/** One send's page: the counts, the message, and every person's result. */
export function SentDetailPage(): JSX.Element {
  const id = Number(useParams().id);
  const email = useBulkEmail(id);
  const me = useMe();
  const sender = useBulkSender();

  if (email.isError) {
    return (
      <Page title="Sent bulk email" eyebrow="Bulk Email">
        <p className="field__error" role="alert">
          This email could not be loaded. <Link to="/bulk-email/sent">See every sent email</Link>.
        </p>
      </Page>
    );
  }
  if (email.data === undefined) return <Loading />;
  const sent = email.data;
  // A DART leader may read another leader's email to their DART, and stop a callout's
  // reminders, but acts on no other email of theirs.
  const canAct = sender.data?.is_management === true || me.data?.id === sent.sender_id;
  const canStop = canAct || sent.is_callout;

  return (
    <Page title={sent.subject || 'Sent bulk email'} eyebrow="Bulk Email" lede={sentLede(sent)}>
      <Card title="Where it stands">
        {sent.started_at === null ? (
          <p>
            This email has not started sending.{' '}
            <Link to={`/bulk-email/compose/${sent.id}`}>Open it</Link>.
          </p>
        ) : (
          <SendStatus email={sent} canAct={canAct} canStop={canStop} />
        )}
        {sent.is_callout && sent.started_at !== null ? (
          <p>
            This is a mission callout.{' '}
            <Link to={`/bulk-email/callouts/${sent.id}`}>See who can fly</Link>.
          </p>
        ) : null}
        {canAct ? (
          <DuplicateButton emailId={sent.id} subject={sent.subject} />
        ) : (
          <p className="muted">
            {sent.sender || 'Another sender'} sent this email to your DART. You can read it here.
          </p>
        )}
      </Card>

      <Card title="The message">
        <p className="muted">Type: {sent.email_type_name || 'None'}</p>
        <p className="muted">Replies go to: {sent.reply_to || sent.default_reply_to}</p>
        {hasFields(sent) ? (
          <p className="muted">
            Fields such as {'{first_name}'} show as written here; each person&apos;s copy had their
            own details filled in.
          </p>
        ) : null}
        <EmailFrame title="The message as it was sent" html={sent.message_html} />
        {sent.started_at === null ? null : <MessagesVisibility email={sent} />}
      </Card>

      <Card title="Who received it">
        <DeliveryReport email={sent} canRetry={canAct} />
      </Card>
    </Page>
  );
}

/** A recipient field token, `{first_name}` or `{first_name|friend}`, as the server reads one. */
const TOKEN = /(?<!\{)\{[a-z][a-z0-9_]*(?:\|[^{}|<>\n]*)?\}(?!\})/;

/** Whether `email`'s subject or message fills in a recipient field. */
export function hasFields(email: Pick<BulkEmailDetail, 'subject' | 'body'>): boolean {
  return TOKEN.test(email.subject) || TOKEN.test(email.body);
}

/**
 * `Sent by Grace Holloway on 04/06/2026 at 10:00 AM.`: who and when. How many it went
 * to is the result line's, so the page gives that number once.
 */
function sentLede(email: BulkEmailDetail): string {
  const from = email.sender ? `Sent by ${email.sender}` : 'Sent';
  const when = email.started_at === null ? '' : ` on ${formatDateAt(email.started_at)}`;
  return `${from}${when}.`;
}
