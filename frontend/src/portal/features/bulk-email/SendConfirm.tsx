/**
 * The confirmation Send and Schedule open: what goes to how many people, and
 * when. Above the size `confirmAbove` it asks the sender to type the number of
 * people, and the button that sends stays off until the number matches; the
 * server checks the number again, in case the batch changed meanwhile.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { formatCountdown } from './countdown';
import { people } from './status';

/** What the scheduled time's zone is called: the site's own, where CalDART flies. */
export const SITE_TIME_ZONE_NAME = 'Pacific time';

interface SendConfirmProps {
  subject: string;
  count: number;
  confirmAbove: number;
  undoSeconds: number;
  /** The chosen start, `YYYY-MM-DDTHH:MM` in the site's time zone, or null for now. */
  startAt: string | null;
  /** Sends; rejects to keep the confirmation open while the card shows why. */
  onConfirm: (typedCount: number | null) => Promise<void>;
  onBack: () => void;
}

/**
 * `04/07/2026 at 08:00`: a chosen start as the confirmation reads it.
 *
 * @param startAt `YYYY-MM-DDTHH:MM`.
 */
export function scheduledWords(startAt: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})/.exec(startAt);
  if (match === null) return startAt;
  const [, year, month, day, time] = match;
  return `${month}/${day}/${year} at ${time}`;
}

/** When the send starts, in words, for the confirmation. */
function whenWords(startAt: string | null, undoSeconds: number): string {
  if (startAt !== null) return `It goes out on ${scheduledWords(startAt)} ${SITE_TIME_ZONE_NAME}.`;
  if (undoSeconds <= 0) return 'Sending starts within a minute.';
  return `Sending starts in ${formatCountdown(undoSeconds)}, and until then you can cancel it.`;
}

/** The confirmation panel, with the typed count when the batch is large. */
export function SendConfirm({
  subject,
  count,
  confirmAbove,
  undoSeconds,
  startAt,
  onConfirm,
  onBack: handleBack,
}: SendConfirmProps): JSX.Element {
  const [typed, setTyped] = useState('');
  const [isPending, setIsPending] = useState(false);
  const needsCount = count > confirmAbove;
  const isConfirmed = !needsCount || Number(typed.trim()) === count;
  const label = startAt === null ? 'Send now' : 'Schedule it';

  const handleConfirm = (): void => {
    setIsPending(true);
    void onConfirm(needsCount ? Number(typed.trim()) : null)
      .catch(() => undefined)
      .finally(() => setIsPending(false));
  };

  return (
    <section className="stack-tight bulk-email__confirm" aria-label="Confirm sending">
      <p>
        This sends <strong>{subject}</strong> to {people(count)}. {whenWords(startAt, undoSeconds)}
      </p>
      {needsCount ? (
        <Field
          label={`Type ${count} to confirm`}
          hint="A large send asks for its number, so the wrong batch is never sent by accident."
        >
          {(field) => (
            <input
              {...field}
              type="text"
              inputMode="numeric"
              autoComplete="off"
              className="mono bulk-email__count"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
            />
          )}
        </Field>
      ) : null}
      <div className="cluster">
        <Button onClick={handleConfirm} disabled={!isConfirmed || isPending}>
          {isPending ? 'Sending…' : label}
        </Button>
        <Button variant="quiet" onClick={handleBack} disabled={isPending}>
          Go back
        </Button>
      </div>
    </section>
  );
}
