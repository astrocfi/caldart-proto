/**
 * The confirmation Send and Schedule open: what goes to how many people, and
 * when. Above the size `confirmAbove` it asks the sender to type the number of
 * people, and the button that sends stays off until the number matches; the
 * server checks the number again, in case the batch changed meanwhile.
 *
 * The focus starts in the number box, or on **Go back** when there is none, so a
 * second press of Enter does not send by accident; the Escape key goes back, as
 * **Go back** does.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, KeyboardEvent } from 'react';

import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { formatDuration } from './countdown';
import { chosenWords } from './schedule';
import { people } from './status';

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

/** When the send starts, in words, for the confirmation. */
function whenWords(startAt: string | null, undoSeconds: number): string {
  if (startAt !== null) return `It goes out on ${chosenWords(startAt)}.`;
  if (undoSeconds <= 0) return 'Sending starts within a minute.';
  return `Sending starts in ${formatDuration(undoSeconds)}, and until then you can cancel it.`;
}

/** The sentence a typed number that is not the count shows. */
export function mismatchMessage(count: number): string {
  return `That number does not match. Type ${count}, the number of people who will receive it.`;
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
  const countRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLButtonElement>(null);
  const needsCount = count > confirmAbove;
  const typedNumber = typed.trim();
  const isConfirmed = !needsCount || Number(typedNumber) === count;
  const isMismatch = needsCount && typedNumber !== '' && !isConfirmed;
  const label = startAt === null ? 'Send now' : 'Schedule it';

  useEffect(() => {
    (needsCount ? countRef.current : backRef.current)?.focus();
  }, [needsCount]);

  const handleConfirm = (): void => {
    setIsPending(true);
    void onConfirm(needsCount ? Number(typedNumber) : null)
      .catch(() => undefined)
      .finally(() => setIsPending(false));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>): void => {
    if (event.key !== 'Escape' || isPending) return;
    event.stopPropagation();
    handleBack();
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
          error={isMismatch ? mismatchMessage(count) : null}
        >
          {(field) => (
            <input
              {...field}
              ref={countRef}
              type="text"
              inputMode="numeric"
              autoComplete="off"
              className="bulk-email__count"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
      ) : null}
      <div className="cluster">
        <Button
          onClick={handleConfirm}
          onKeyDown={handleKeyDown}
          disabled={!isConfirmed || isPending}
        >
          {isPending ? 'Sending…' : label}
        </Button>
        <Button
          ref={backRef}
          variant="quiet"
          onClick={handleBack}
          onKeyDown={handleKeyDown}
          disabled={isPending}
        >
          Go back
        </Button>
      </div>
    </section>
  );
}
