/**
 * `/messages/:id`: one bulk email the signed-in person received, exactly as their
 * copy went, with their own details filled in.
 *
 * The **View this email in your browser** link in every bulk email opens this page.
 * The email is drawn in a sandboxed frame, so nothing in it can run or reach the
 * portal, and its links open in a new tab. An email the person did not receive, or one CalDART management has taken
 * off Messages, reads as not available.
 */
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailMessageDetail } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { EmailFrame } from '@/portal/components/EmailFrame';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { useMessage } from './api';

/** What the page says for an email that is not the reader's to read. */
export const NOT_AVAILABLE_MESSAGE =
  'This message is not available. It may not have been sent to you, or it has been taken off Messages.';

/** What the page says when the message could not be loaded for another reason. */
const FALLBACK_ERROR = 'This message could not be loaded. Try again in a moment.';

/** One message, as the reader's own copy. */
export function MessagePage(): JSX.Element {
  const id = Number(useParams().id);
  const message = useMessage(id);

  if (message.isError) {
    const isMissing = message.error instanceof ApiError && message.error.status === 404;
    return (
      <Page title="Message" eyebrow="Bulk Email">
        <p className="field__error" role="alert">
          {isMissing ? NOT_AVAILABLE_MESSAGE : FALLBACK_ERROR}{' '}
          <Link to="/messages">See all your messages</Link>.
        </p>
      </Page>
    );
  }
  if (message.data === undefined) return <Loading />;
  const shown = message.data;

  return (
    <Page title={shown.subject || 'Message'} eyebrow="Bulk Email" lede={fromLine(shown)}>
      <Card>
        <EmailFrame title={`The email: ${shown.subject}`} html={shown.html} />
        <p>
          <Link to="/messages">See all your messages</Link>
        </p>
      </Card>
    </Page>
  );
}

/** `From Grace Holloway on 04/07/2026, Operational email.` */
export function fromLine(message: BulkEmailMessageDetail): string {
  const kind = message.email_type_name ? `, ${message.email_type_name} email` : '';
  return `From ${message.from_name} on ${formatDate(message.sent_at)}${kind}.`;
}
