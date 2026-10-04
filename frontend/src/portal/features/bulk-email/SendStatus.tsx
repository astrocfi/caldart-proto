/**
 * Where a bulk email stands once Send has been pressed, with the one action that
 * fits: the countdown or the scheduled time with **Cancel**, the copies waiting
 * after Send the rest with **Stop sending**, the progress of a send with **Stop
 * sending**, or the result, with **Send the rest** after a stop.
 *
 * The compose screen shows it as the banner over its cards, and the Sent detail page
 * under its heading.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { useToast } from '@/portal/components/Toast';
import { useBulkEmailAction } from './api';
import { formatCountdown, useSecondsUntil } from './countdown';
import { scheduledWords } from './schedule';
import { people, progressSentence, progressTotal, resultSentence, wentCount } from './status';

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
  /**
   * False for somebody who may read the email but not act on it, a DART leader reading
   * another leader's email to their DART: **Cancel** and **Send the rest** are left out.
   */
  canAct?: boolean;
  /** False to leave out **Stop sending** too; it follows `canAct` unless given. */
  canStop?: boolean;
}

/**
 * A queued email: *Sending in 1 min 58 s* with the undo window's bar and **Cancel**,
 * *Scheduled for 10/04/2026 at 8:00 AM Pacific time* with **Cancel the schedule**, or,
 * after Send the rest, the copies waiting with **Stop sending**.
 */
export function QueuedStatus({ email, canAct = true, canStop = canAct }: StatusProps): JSX.Element {
  if (email.started_at !== null) return <WaitingForTheRest email={email} canStop={canStop} />;
  return <Countdown email={email} canAct={canAct} />;
}

/** An email that has never started, waiting out its undo window or its scheduled time. */
function Countdown({ email, canAct = true }: StatusProps): JSX.Element {
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
          <strong>Scheduled for {scheduledWords(email.start_at)}.</strong> You can still change it
          until then.
        </p>
      ) : seconds > 0 ? (
        <>
          <p>
            <strong>Sending in {formatCountdown(seconds)}</strong> to{' '}
            {people(email.receiving_count)}. Until then you can cancel it, and nothing is sent.
          </p>
          <progress
            className="bulk-email__progress"
            aria-label="Time left before sending starts"
            max={Math.max(email.undo_seconds, 1)}
            value={Math.max(0, email.undo_seconds - seconds)}
          />
        </>
      ) : (
        <p>
          <strong>Starting to send.</strong> Nothing has been sent yet. You can still cancel until
          the first copy goes out.
        </p>
      )}
      {canAct ? (
        <div className="cluster">
          <Button variant="secondary" onClick={handleCancel} disabled={cancel.isPending}>
            {email.scheduled ? 'Cancel the schedule' : 'Cancel'}
          </Button>
        </div>
      ) : null}
      {cancel.isError ? (
        <p className="field__error" role="alert">
          {actionError(cancel.error)}
        </p>
      ) : null}
    </div>
  );
}

/** An email Send the rest queued again: it goes within a minute, and can be stopped. */
function WaitingForTheRest({ email, canStop = true }: StatusProps): JSX.Element {
  return (
    <div className="stack-tight bulk-email__status">
      <p>
        <strong>Waiting to send the rest.</strong> The {people(email.remaining)} not sent a copy yet
        will be sent one within a minute.
      </p>
      {canStop ? <StopButton email={email} /> : null}
    </div>
  );
}

/** A send in progress: *Sending… 12 of 38 sent, about 1 minute left.*, a bar, and Stop. */
export function SendingStatus({ email, canStop = true }: StatusProps): JSX.Element {
  const tried = wentCount(email) + email.failed_count;
  const total = progressTotal(email);

  return (
    <div className="stack-tight bulk-email__status">
      <p role="status">
        {email.stop_requested ? 'Stopping after the copy now going out…' : progressSentence(email)}
      </p>
      <progress
        className="bulk-email__progress"
        aria-label="Copies sent so far"
        max={Math.max(total, 1)}
        value={tried}
      />
      {email.stop_requested || !canStop ? null : <StopButton email={email} />}
    </div>
  );
}

/** **Stop sending**, behind a confirmation, with what happens after. */
function StopButton({ email }: StatusProps): JSX.Element {
  const stop = useBulkEmailAction('stop');
  const toast = useToast();

  return (
    <>
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
            Copies already sent cannot be called back. Everyone who has not been sent a copy yet is
            marked <em>Not sent (stopped)</em>, and you can send them the rest later.
          </p>
        </ConfirmButton>
      </div>
      {stop.isError ? (
        <p className="field__error" role="alert">
          {actionError(stop.error)}
        </p>
      ) : null}
    </>
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
  canAct = true,
}: FinishedStatusProps): JSX.Element {
  const resume = useBulkEmailAction('resume');
  const toast = useToast();
  const unsent = email.batch_count - wentCount(email) - email.failed_count - email.skipped_count;

  return (
    <div className="stack-tight bulk-email__status">
      <p role="status">{resultSentence(email)}</p>
      <div className="cluster">
        {email.status === 'stopped' && canAct ? (
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
export function SendStatus({
  email,
  isDetailLinked = false,
  canAct = true,
  canStop = canAct,
}: FinishedStatusProps): JSX.Element {
  if (email.status === 'queued') {
    return <QueuedStatus email={email} canAct={canAct} canStop={canStop} />;
  }
  if (email.status === 'sending') return <SendingStatus email={email} canStop={canStop} />;
  if (email.status === 'sent' || email.status === 'stopped') {
    return <FinishedStatus email={email} isDetailLinked={isDetailLinked} canAct={canAct} />;
  }
  return <></>;
}
