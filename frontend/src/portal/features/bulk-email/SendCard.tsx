/**
 * Card 3 of the compose screen, **Check and send**.
 *
 * While the email is a draft it says what is still missing, if anything, then
 * offers **Send to 38 people** and **Schedule for later**. Either asks first, in
 * a confirmation that says what goes to how many people and when; above the
 * size `confirm_above` the sender types the number of people before the button
 * that sends works. Once Send is pressed the card follows the email: the
 * countdown with **Cancel**, the progress with **Stop**, then the result.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { useSendBulkEmail } from './api';
import { ScheduleFields } from './ScheduleFields';
import { SendConfirm } from './SendConfirm';
import { SendStatus } from './SendStatus';
import { sendLabel } from './status';

/** What the card says when the send fails without a message of its own. */
const FALLBACK_ERROR = 'The email could not be sent. Try again.';

/** What the card says when the latest words could not be saved before sending. */
const NOT_SAVED_MESSAGE =
  'Your latest changes could not be saved, so the email was not sent. Try again in a moment.';

/** The fields a refused send names, in the order the card lists them. */
const SEND_FIELDS = ['subject', 'body', 'batch', 'confirm_count', 'start_at'] as const;

/** Where the card is in the sender's steps. */
type Step = { kind: 'choose' } | { kind: 'confirm'; startAt: string | null } | { kind: 'schedule' };

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
  email: Pick<BulkEmailDetail, 'receiving_count'>,
  subject: string,
  body: string,
): string[] {
  return [
    ...(subject.trim() === '' ? ['Write a subject.'] : []),
    ...(body.trim() === '' ? ['Write the message.'] : []),
    ...(email.receiving_count === 0 ? ['Add people to the batch.'] : []),
  ];
}

/** The send controls, or where the email stands once they have been used. */
export function SendCard({
  email,
  subject,
  body,
  onBeforeSend: handleBeforeSend,
}: SendCardProps): JSX.Element {
  const [step, setStep] = useState<Step>({ kind: 'choose' });
  const [saveError, setSaveError] = useState<Error | null>(null);
  const send = useSendBulkEmail(email.id);
  const missing = missingSteps(email, subject, body);

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
    setStep({ kind: 'choose' });
  };

  return (
    <Card title="3. Check and send" className="bulk-email__card">
      {email.status === 'draft' ? (
        <p className="muted">
          Read the email through, then send it now or choose a time. You can cancel a send for a
          short while after you press Send.
        </p>
      ) : null}

      <SendStatus email={email} isDetailLinked />

      {email.status === 'draft' || (email.status === 'queued' && email.scheduled) ? (
        <DraftControls
          email={email}
          subject={subject}
          missing={missing}
          step={step}
          onStep={handleStep}
          onSend={handleSend}
          error={saveError ?? send.error}
        />
      ) : null}
    </Card>
  );
}

interface DraftControlsProps {
  email: BulkEmailDetail;
  subject: string;
  missing: string[];
  step: Step;
  onStep: (step: Step) => void;
  onSend: (typedCount: number | null) => Promise<void>;
  error: unknown;
}

/** What is missing, then the two buttons, the scheduler, or the confirmation. */
function DraftControls({
  email,
  subject,
  missing,
  step,
  onStep: handleStep,
  onSend: handleSend,
  error,
}: DraftControlsProps): JSX.Element {
  const isRescheduling = email.status === 'queued';

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
          onBack={() => handleStep({ kind: 'choose' })}
        />
        <SendErrors error={error} />
      </div>
    );
  }

  if (step.kind === 'schedule') {
    return (
      <ScheduleFields
        onChoose={(startAt) => handleStep({ kind: 'confirm', startAt })}
        onBack={() => handleStep({ kind: 'choose' })}
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
    <div className="cluster">
      {isRescheduling ? null : (
        <Button onClick={() => handleStep({ kind: 'confirm', startAt: null })}>
          {sendLabel(email.receiving_count)}
        </Button>
      )}
      <Button variant="secondary" onClick={() => handleStep({ kind: 'schedule' })}>
        {isRescheduling ? 'Change the time' : 'Schedule for later'}
      </Button>
    </div>
  );
}

/** Each reason the server gave for refusing the send, one per line. */
function SendErrors({ error }: { error: unknown }): JSX.Element | null {
  if (error === null || error === undefined) return null;
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
