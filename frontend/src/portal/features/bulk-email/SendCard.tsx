/**
 * Card 3 of the compose screen, **Check and send**, shown while the email can
 * still be sent or rescheduled.
 *
 * It opens with the checks (`ChecksList`), run when the card opens and again
 * before the confirmation, and the preview. For a draft it says what is still
 * missing, if anything, then offers **Send to 38 people** and **Schedule for
 * later**, which stay off while the checks list a problem that must be fixed;
 * a press that finds one puts the focus on **Check again**. Checks that fail or
 * are slow do not stop a send: the server refuses an email with an error anyway. Either asks first,
 * in a confirmation that says what goes to how many people and when; above the size `confirm_above` the
 * sender types the number of people before the button that sends works. For a
 * scheduled email it offers **Change the time**, which opens at the time already
 * chosen, and **Send now instead**. Once Send is pressed, where the email stands is
 * the banner at the top of the screen.
 *
 * Going back from the confirmation or the schedule puts the focus back on the
 * button that opened it.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { useSendBulkEmail } from './api';
import { ChecksList, shownFindings } from './ChecksList';
import { hasError, refusedFindings, useBulkEmailChecks } from './checksApi';
import { MessagePreview } from './MessagePreview';
import { ScheduleFields } from './ScheduleFields';
import { sitePartsOf } from './schedule';
import { SendConfirm } from './SendConfirm';
import { sendLabel } from './status';

/** What the card says when the send fails without a message of its own. */
const FALLBACK_ERROR = 'The email could not be sent. Try again.';

/** What the card says when the latest words could not be saved before sending. */
const NOT_SAVED_MESSAGE =
  'Your latest changes could not be saved, so the email was not sent. Try again in a moment.';

/**
 * How long Send waits for the checks before opening the confirmation without them.
 * The server refuses an email with an error whatever the checks on screen said, so
 * slow or failing checks never keep a sender from sending.
 */
export const CHECKS_WAIT_MS = 8000;

/** `promise`'s value, or null once it fails or `ms` pass without it. */
async function withinTime<T>(promise: Promise<T>, ms: number): Promise<T | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), ms);
  });
  try {
    return await Promise.race([promise.catch(() => null), late]);
  } finally {
    clearTimeout(timer);
  }
}

/** The fields a refused send names, in the order the card lists them. */
const SEND_FIELDS = ['subject', 'body', 'batch', 'confirm_count', 'start_at'] as const;

/** The button a step opened from, which the focus goes back to. */
type Opener = 'send' | 'schedule';

/** Where the card is in the sender's steps. */
type Step =
  | { kind: 'choose'; returnTo: Opener | 'checks' | null }
  | { kind: 'confirm'; startAt: string | null; from: Opener }
  | { kind: 'schedule' };

interface SendCardProps {
  email: BulkEmailDetail;
  /** The subject and message as typed, which may be ahead of `email`'s. */
  subject: string;
  body: string;
  /** Save what is typed before sending; resolves true once it is saved. */
  onBeforeSend: () => Promise<boolean>;
}

/** What is still missing before the email can go, as short instructions. */
export function missingSteps(
  email: Pick<BulkEmailDetail, 'receiving_count' | 'email_type'>,
  subject: string,
  body: string,
): string[] {
  return [
    ...(email.email_type === null ? ['Choose a type.'] : []),
    ...(subject.trim() === '' ? ['Write a subject.'] : []),
    ...(body.trim() === '' ? ['Write the message.'] : []),
    ...(email.receiving_count === 0 ? ['Add people to the batch.'] : []),
  ];
}

/** The send controls of a draft, or the rescheduling controls of a scheduled email. */
export function SendCard({
  email,
  subject,
  body,
  onBeforeSend: handleBeforeSend,
}: SendCardProps): JSX.Element {
  const [step, setStep] = useState<Step>({ kind: 'choose', returnTo: null });
  const [saveError, setSaveError] = useState<Error | null>(null);
  const send = useSendBulkEmail(email.id);
  const isScheduled = email.status === 'queued';
  const missing = missingSteps(email, subject, body);
  const sendRef = useRef<HTMLButtonElement>(null);
  const scheduleRef = useRef<HTMLButtonElement>(null);
  const checkAgainRef = useRef<HTMLButtonElement>(null);
  const checks = useBulkEmailChecks(email.id);
  const { mutate: runChecks, mutateAsync: runChecksAsync } = checks;
  const isBlocked = checks.data !== undefined && hasError(shownFindings(checks.data));

  useEffect(() => {
    runChecks();
  }, [runChecks]);

  useEffect(() => {
    if (step.kind !== 'choose' || step.returnTo === null) return;
    const refs = { send: sendRef, schedule: scheduleRef, checks: checkAgainRef };
    refs[step.returnTo].current?.focus();
  }, [step]);

  const handleStep = (next: Step): void => {
    setSaveError(null);
    send.reset();
    setStep(next);
  };

  const handleSend = async (typedCount: number | null): Promise<void> => {
    if (step.kind !== 'confirm') return;
    setSaveError(null);
    const isSaved = await handleBeforeSend();
    if (!isSaved) {
      const error = new Error(NOT_SAVED_MESSAGE);
      setSaveError(error);
      throw error;
    }
    await send.mutateAsync({ confirm_count: typedCount, start_at: step.startAt });
    setStep({ kind: 'choose', returnTo: null });
  };

  // The confirmation opens once the latest words are saved and the checks, run on
  // them afresh, find nothing that must be fixed; the list says what. Checks that
  // fail, or take longer than CHECKS_WAIT_MS, do not hold it back.
  const handleConfirmStep = async (next: {
    startAt: string | null;
    from: Opener;
  }): Promise<void> => {
    setSaveError(null);
    send.reset();
    const isSaved = await handleBeforeSend();
    if (!isSaved) {
      setStep({ kind: 'choose', returnTo: null });
      setSaveError(new Error(NOT_SAVED_MESSAGE));
      return;
    }
    // A failure stays on the checks' own state, which the list shows with Check again.
    const found = await withinTime(runChecksAsync(), CHECKS_WAIT_MS);
    if (found !== null && hasError(shownFindings(found))) {
      setStep({ kind: 'choose', returnTo: 'checks' });
      return;
    }
    setStep({ kind: 'confirm', ...next });
  };

  // Going back puts the focus on the button that opened the step.
  const handleBack = (): void => {
    handleStep({ kind: 'choose', returnTo: step.kind === 'confirm' ? step.from : 'schedule' });
  };

  const controls = (): JSX.Element => {
    if (step.kind === 'confirm') {
      return (
        <div className="stack-tight">
          <SendConfirm
            subject={subject}
            count={email.receiving_count}
            confirmAbove={email.confirm_above}
            undoSeconds={email.undo_seconds}
            startAt={step.startAt}
            onConfirm={handleSend}
            onBack={handleBack}
          />
          <SendErrors error={saveError ?? send.error} />
        </div>
      );
    }
    if (step.kind === 'schedule') {
      return (
        <ScheduleFields
          initial={isScheduled && email.start_at !== null ? sitePartsOf(email.start_at) : undefined}
          onChoose={(startAt) => void handleConfirmStep({ startAt, from: 'schedule' })}
          onBack={handleBack}
        />
      );
    }
    if (missing.length > 0) {
      return (
        <div className="stack-tight">
          <p>Before you can send it:</p>
          <ul>
            {missing.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      );
    }
    return (
      <div className="stack-tight">
        <div className="cluster bulk-email__send-choices">
          <Button
            ref={sendRef}
            variant={isScheduled ? 'secondary' : 'primary'}
            disabled={isBlocked}
            onClick={() => void handleConfirmStep({ startAt: null, from: 'send' })}
          >
            {isScheduled ? 'Send now instead' : sendLabel(email.receiving_count)}
          </Button>
          <Button
            ref={scheduleRef}
            variant="secondary"
            disabled={isBlocked}
            onClick={() => handleStep({ kind: 'schedule' })}
          >
            {isScheduled ? 'Change the time' : 'Schedule for later'}
          </Button>
        </div>
        <SendErrors error={saveError} />
      </div>
    );
  };

  return (
    <Card title="3. Check and send" className="bulk-email__card">
      <p className="muted">
        {isScheduled
          ? 'Change when it goes out, or send it now instead. Cancel the schedule at the top of the screen.'
          : 'Read the email through, then send it now or choose a time. You can cancel a send for a short while after you press Send.'}
      </p>
      <ChecksList
        checkAgainRef={checkAgainRef}
        findings={checks.data}
        isChecking={checks.isPending}
        error={checks.error}
        onCheckAgain={() => runChecks()}
      />
      <MessagePreview email={email} />
      {controls()}
    </Card>
  );
}

/** Each reason the server gave for refusing the send, one per line. */
function SendErrors({ error }: { error: unknown }): JSX.Element | null {
  if (error === null || error === undefined) return null;
  const findings = refusedFindings(error);
  if (findings !== null) {
    return (
      <div className="field__error" role="alert">
        {findings.map((finding) => (
          <p key={`${finding.code}:${finding.message}`}>{finding.message}</p>
        ))}
      </div>
    );
  }
  if (!(error instanceof ApiError)) {
    return (
      <p className="field__error" role="alert">
        {error instanceof Error ? error.message : FALLBACK_ERROR}
      </p>
    );
  }
  const fields = error.fieldErrors;
  const lines = SEND_FIELDS.flatMap((key) => (fields[key] === undefined ? [] : [fields[key]]));
  return (
    <div className="field__error" role="alert">
      {(lines.length > 0 ? lines : [error.message]).map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}
