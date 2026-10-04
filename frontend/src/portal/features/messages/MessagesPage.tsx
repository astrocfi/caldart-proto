/**
 * `/messages`: the bulk emails the signed-in person received, newest first.
 *
 * Each line is one email: when it was sent to them, its subject as their copy had
 * it, who sent it, and its type. The subject opens the email, or, for a mission
 * callout, the reader's own answer page, which shows the message beside the answer.
 * Only bulk email is here; receipts, reminders, and other mail about the person's own
 * account are not.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailMessage } from '@/portal/api/types';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { useMessages } from './api';

/** Every bulk email the signed-in person received. */
export function MessagesPage(): JSX.Element {
  const messages = useMessages();
  const rows = messages.data ?? [];

  return (
    <Page title="Messages" lede="Copies of the emails CalDART sent to members and friends.">
      <Card>
        {messages.isError ? (
          <p className="field__error" role="alert">
            Your messages didn&apos;t load. Try again in a moment.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={MESSAGE_COLUMNS}
            rows={rows}
            rowKey={(row) => row.id}
            initialSort={{ key: 'sent_at', direction: 'desc' }}
            caption={`${rows.length} ${rows.length === 1 ? 'message' : 'messages'}`}
            emptyTitle="No messages yet"
            emptyDescription="When CalDART emails its members and friends, the email appears here too."
            emptyAction={
              <ButtonLink to="/email-preferences" variant="secondary">
                Email preferences
              </ButtonLink>
            }
            isLoading={messages.isLoading}
          />
        )}
        <p className="muted">
          Email about your own account, such as receipts, renewal reminders, and password links, is
          not listed here.
        </p>
      </Card>
    </Page>
  );
}

/**
 * The list's columns, the date first and then the subject, which opens the email, or a
 * callout's answer page, and tells the rows apart. The type, then who sent it, give way
 * when the table would not fit its card.
 */
export const MESSAGE_COLUMNS: Column<BulkEmailMessage>[] = [
  {
    key: 'sent_at',
    header: 'Date',
    width: '6.5rem',
    noWrap: true,
    render: (row) => <DateText value={row.sent_at} />,
    sortValue: (row) => row.sent_at,
  },
  {
    key: 'subject',
    header: 'Subject',
    minWidth: '16rem',
    isIdentity: true,
    render: (row) =>
      row.answer_url === '' ? (
        <Link to={`/messages/${row.id}`}>{row.subject || '(no subject)'}</Link>
      ) : (
        <a href={row.answer_url}>{row.subject || '(no subject)'}</a>
      ),
    sortValue: (row) => row.subject,
  },
  {
    key: 'from_name',
    header: 'From',
    minWidth: '9rem',
    dropOrder: 2,
    render: (row) => row.from_name,
    sortValue: (row) => row.from_name,
  },
  {
    key: 'email_type_name',
    header: 'Type',
    width: '7rem',
    dropOrder: 1,
    render: (row) => row.email_type_name || '—',
    sortValue: (row) => row.email_type_name,
  },
];
