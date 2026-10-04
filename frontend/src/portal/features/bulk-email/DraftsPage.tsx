/**
 * `/bulk-email/drafts`: Drafts & scheduled. One line per bulk email not yet
 * started: every draft, every email waiting out its undo window, and every
 * scheduled one, the most recently edited first.
 *
 * The subject opens the email's compose screen. A queued email has **Cancel
 * schedule**, which turns it back into a draft, and a draft has a trashcan,
 * which asks before it deletes. An email the background sender returned unsent,
 * because its sender may no longer send its type, is named above the table with
 * the reason. CalDART management, who sees every sender's emails, also sees who
 * wrote each and the DART a DART leader's email goes to. A DART leader whose profile
 * names no DART is told to set it on My profile, in place of **Write a new email**.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailSummary } from '@/portal/api/types';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText, formatDateTime } from '@/portal/components/DateText';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { DROP_ORDER } from './dropOrder';
import { useBulkEmailAction, useBulkSender, useDeleteDraft, useDrafts } from './api';
import './bulk-email.css';
import { formatCountdown, useSecondsUntil } from './countdown';
import { SenderNotice } from './SenderNotice';
import { withSenderColumns } from './senderColumns';
import { actionError, CANCELED_MESSAGE } from './SendStatus';
import { statusLabel, statusTone } from './status';

/** What a draft with no subject yet is listed as. */
export const NO_SUBJECT = '(no subject yet)';

/** The drafts and queued emails, each opened by its subject, with Cancel and the trashcan. */
export function DraftsPage(): JSX.Element {
  const drafts = useDrafts();
  const sender = useBulkSender();
  const cancel = useBulkEmailAction('cancel');
  const remove = useDeleteDraft();
  const toast = useToast();
  const rows = drafts.data ?? [];

  const handleCancel = (id: number): void => {
    cancel.mutate(id, { onSuccess: () => toast.show(CANCELED_MESSAGE, 'success') });
  };

  const handleDelete = (id: number): Promise<unknown> =>
    remove.mutateAsync(id).then(() => toast.show('The draft was deleted.', 'success'));

  const failure = cancel.error ?? remove.error;
  const notSent = rows.filter((row) => row.not_sent_reason !== '');
  // A DART leader with no DART on their profile cannot write one, so the screen says
  // how to fix that rather than how to start one.
  const cannotSend = sender.data?.can_send === false;

  return (
    <Page
      title="Drafts and scheduled"
      lede="Emails still being written, and emails waiting for their time to send."
      actions={
        cannotSend ? null : <ButtonLink to="/bulk-email/compose">Write a new email</ButtonLink>
      }
    >
      {sender.data === undefined ? null : <SenderNotice sender={sender.data} />}
      <Card>
        {failure === null ? null : (
          <p className="field__error" role="alert">
            {actionError(failure)}
          </p>
        )}
        {notSent.length === 0 ? null : (
          <ul className="bulk-email__not-sent stack-tight" aria-label="Emails that were not sent">
            {notSent.map((row) => (
              <li key={row.id} className="bulk-email__notice">
                <Link to={`/bulk-email/compose/${row.id}`}>{row.subject || NO_SUBJECT}</Link>:{' '}
                {row.not_sent_reason}
              </li>
            ))}
          </ul>
        )}
        {drafts.isError ? (
          <p className="field__error" role="alert">
            The drafts could not be loaded.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={withSenderColumns(
              draftColumns(handleCancel, handleDelete),
              sender.data?.is_management === true,
            )}
            rows={rows}
            rowKey={(row) => row.id}
            caption={`${rows.length} ${rows.length === 1 ? 'email' : 'emails'} not sent yet`}
            emptyTitle="No drafts"
            emptyDescription={cannotSend ? undefined : 'Press Write a new email to start one.'}
            emptyAction={
              cannotSend ? undefined : (
                <ButtonLink to="/bulk-email/compose">Write a new email</ButtonLink>
              )
            }
            isLoading={drafts.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}

/**
 * The table's columns, wired to the two row actions: the subject, which tells the rows
 * apart, and last the actions, which stay in sight on a narrow screen. The type, the
 * DART, when it was last edited, and who wrote it give way, in that order, when the
 * table would not fit its card.
 */
function draftColumns(
  onCancel: (id: number) => void,
  onDelete: (id: number) => Promise<unknown>,
): Column<BulkEmailSummary>[] {
  return [
    {
      key: 'subject',
      header: 'Subject',
      minWidth: '14rem',
      isIdentity: true,
      render: (row) => (
        <Link to={`/bulk-email/compose/${row.id}`}>{row.subject || NO_SUBJECT}</Link>
      ),
      sortValue: (row) => row.subject,
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '10rem',
      isActions: true,
      render: (row) => (
        <span className="cluster cluster--nowrap">
          {row.status === 'queued' ? (
            <Button
              variant="quiet"
              small
              aria-label={`Cancel the send of ${row.subject || NO_SUBJECT}`}
              onClick={() => onCancel(row.id)}
            >
              {row.scheduled ? 'Cancel schedule' : 'Cancel'}
            </Button>
          ) : (
            <DeleteButton
              label={`Delete the draft ${row.subject || NO_SUBJECT}`}
              onDelete={() => onDelete(row.id)}
            />
          )}
        </span>
      ),
    },
    {
      key: 'email_type_name',
      header: 'Type',
      width: '7rem',
      dropOrder: DROP_ORDER.type,
      render: (row) => row.email_type_name || '—',
      sortValue: (row) => row.email_type_name,
    },
    {
      key: 'status',
      header: 'Status',
      width: '8rem',
      render: (row) => (
        <span className="bulk-email__will-receive">
          <StatusDot tone={statusTone(row.status)} label={statusLabel(row)} />
        </span>
      ),
      sortValue: (row) => statusLabel(row),
    },
    {
      key: 'when',
      header: 'When',
      width: '11.5rem',
      render: (row) => <When row={row} />,
    },
    {
      key: 'batch_count',
      header: 'People',
      numeric: true,
      width: '5rem',
      render: (row) => row.batch_count,
      sortValue: (row) => row.batch_count,
    },
    {
      key: 'updated_at',
      header: 'Last edited',
      width: '6.5rem',
      noWrap: true,
      dropOrder: DROP_ORDER.lastEdited,
      render: (row) => <DateText value={row.updated_at} />,
      sortValue: (row) => row.updated_at,
    },
  ];
}

/** *Scheduled for* a time, *Starts in* a countdown, or a dash for a draft. */
function When({ row }: { row: BulkEmailSummary }): JSX.Element {
  const seconds = useSecondsUntil(row.status === 'queued' ? row.start_at : null);
  if (row.status !== 'queued' || seconds === null) return <span className="muted">—</span>;
  if (row.scheduled) {
    return <span>{formatDateTime(row.start_at)}</span>;
  }
  return <span>{seconds > 0 ? `Starts in ${formatCountdown(seconds)}` : 'Starting now'}</span>;
}
