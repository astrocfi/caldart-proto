/**
 * Where a bulk email stands once Send has been pressed, with the one action that
 * fits: the countdown or the scheduled time with **Cancel**, the progress of a
 * send with **Stop**, or the result, with **Send the rest** after a stop.
 *
 * The compose screen shows it in its Check and send card (and the countdown as a
 * banner at the top), and the Sent detail page under its heading.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { DateText } from '@/portal/components/DateText';
import { useToast } from '@/portal/components/Toast';
import { useBulkEmailAction } from './api';
import { formatCountdown, useSecondsUntil } from './countdown';
import { people, progressSentence, resultSentence } from './status';

/** What the screen says once a queued email is a draft again. */
export const CANCELED_MESSAGE = 'Sending was canceled. The email is a draft again.';

/** What the screen says once Stop has been pressed. */
export const STOPPING_MESSAGE = 'Stopping. Nobody else will be sent a copy.';

/** What the screen says once Send the rest has been pressed. */
export const RESUMED_MESSAGE = 'The rest will start sending within a minute.';

/** What a failed action says when the server gave no sentence of its own. */
const FALLBACK_ERROR = 'That did not work. Try again.';

/** The sentence an action's failure shows. */
export function actionError(error: unknown): string {
  return error instanceof ApiError ? error.message : FALLBACK_ERROR;
}

interface StatusProps {
  email: BulkEmailDetail;
}

/**
 * A queued email: *Sending in 1:58* with the undo window's bar and **Cancel**, or
 * *Scheduled for 04/07/2026 08:00* with **Cancel the schedule**.
 */
export function QueuedStatus({ email }: StatusProps): JSX.Element {
  const seconds = useSecondsUntil(email.start_at) ?? 0;
  const cancel = useBulkEmailAction('cancel');
  const toast = useToast();

  // Canceling is the undo itself and loses nothing, so it acts at once.
  const handleCancel = (): void => {
    cancel.mutate(email.id, {
      onSuccess: () => toast.show(CANCELED_MESSAGE, 'success'),
    });
  };

  return (
    <div className="stack-tight bulk-email__status">
      {email.scheduled ? (
        <p>
          <strong>
            Scheduled for <DateText value={email.start_at} withTime />.
          </strong>{' '}
          You can still change it until then.
        </p>
      ) : (
        <>
          <p>
            <strong>
              {seconds > 0 ? `Sending in ${formatCountdown(seconds)}` : 'Starting to send'}
            </strong>{' '}
            to {people(email.receiving_count)}.{' '}
            {seconds > 0
              ? 'Until then you can cancel it, and nothing is sent.'
              : 'The first copies go out within a minute.'}
          </p>
          <progress
            className="bulk-email__progress"
            aria-label="Time left before sending starts"
            max={Math.max(email.undo_seconds, 1)}
            value={
              seconds > 0
                ? Math.max(0, email.undo_seconds - seconds)
                : Math.max(email.undo_seconds, 1)
            }
          />
        </>
      )}
      <div className="cluster">
        <Button variant="secondary" onClick={handleCancel} disabled={cancel.isPending}>
          {email.scheduled ? 'Cancel the schedule' : 'Cancel'}
        </Button>
      </div>
      {cancel.isError ? (
        <p className="field__error" role="alert">
          {actionError(cancel.error)}
        </p>
      ) : null}
    </div>
  );
}

/** A send in progress: *Sending… 12 of 38 sent, about 1 minute left.*, a bar, and **Stop**. */
export function SendingStatus({ email }: StatusProps): JSX.Element {
  const stop = useBulkEmailAction('stop');
  const toast = useToast();
  const total = email.sent_count + email.failed_count + email.remaining;

  return (
    <div className="stack-tight bulk-email__status">
      <p role="status">
        {email.stop_requested ? 'Stopping after the copy now going out…' : progressSentence(email)}
      </p>
      <progress
        className="bulk-email__progress"
        aria-label="Copies sent so far"
        max={Math.max(total, 1)}
        value={email.sent_count + email.failed_count}
      />
      {email.stop_requested ? null : (
        <div className="cluster">
          <ConfirmButton
            label="Stop sending"
            choices={[
              {
                label: 'Stop now',
                variant: 'danger',
                onChoose: () =>
                  stop.mutateAsync(email.id).then(() => toast.show(STOPPING_MESSAGE, 'success')),
              },
            ]}
          >
            <p>
              Copies already sent cannot be called back. Everyone who has not been sent a copy yet
              is marked <em>Not sent (stopped)</em>, and you can send them the rest later.
            </p>
          </ConfirmButton>
        </div>
      )}
      {stop.isError ? (
        <p className="field__error" role="alert">
          {actionError(stop.error)}
        </p>
      ) : null}
    </div>
  );
}

interface FinishedStatusProps extends StatusProps {
  /** Link to the Sent detail page; left out on that page itself. */
  isDetailLinked?: boolean;
}

/**
 * A send that ended: the counts, a link to who received it, and **Send the rest**
 * after a stop.
 */
export function FinishedStatus({
  email,
  isDetailLinked = false,
}: FinishedStatusProps): JSX.Element {
  const resume = useBulkEmailAction('resume');
  const toast = useToast();
  const unsent = email.batch_count - email.sent_count - email.failed_count - email.skipped_count;

  return (
    <div className="stack-tight bulk-email__status">
      <p role="status">{resultSentence(email)}</p>
      <div className="cluster">
        {email.status === 'stopped' ? (
          <ConfirmButton
            label="Send the rest"
            variant="primary"
            choices={[
              {
                label: 'Send them now',
                onChoose: () =>
                  resume.mutateAsync(email.id).then(() => toast.show(RESUMED_MESSAGE, 'success')),
              },
            ]}
          >
            <p>
              This sends the email to the {people(Math.max(unsent, 0))} who were not sent a copy
              before it was stopped. Nobody already sent a copy gets another.
            </p>
          </ConfirmButton>
        ) : null}
        {isDetailLinked ? (
          <Link className="button button--secondary" to={`/bulk-email/sent/${email.id}`}>
            See who received it
          </Link>
        ) : null}
      </div>
      {resume.isError ? (
        <p className="field__error" role="alert">
          {actionError(resume.error)}
        </p>
      ) : null}
    </div>
  );
}

/** Whichever of the three fits `email`'s status; nothing for a draft. */
export function SendStatus({ email, isDetailLinked = false }: FinishedStatusProps): JSX.Element {
  if (email.status === 'queued') return <QueuedStatus email={email} />;
  if (email.status === 'sending') return <SendingStatus email={email} />;
  if (email.status === 'sent' || email.status === 'stopped') {
    return <FinishedStatus email={email} isDetailLinked={isDetailLinked} />;
  }
  return <></>;
}
