/**
 * **Change closing time** on a callout's page: move when its answers close after it has
 * gone out, for a deployment that runs longer than planned, or shorter.
 *
 * The links already sent keep working until the new time, and a callout whose time ran
 * out takes answers again. A callout closed with **Close now** stays closed, so the page
 * doesn't offer it there.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { CalloutDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { SITE_TIME_ZONE_NAME } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import {
  TIME_CHOICES,
  chosenWords,
  sitePartsOf,
  timeChoice,
} from '@/portal/features/bulk-email/schedule';
import { useMoveCloseTime } from './api';

/** What the form says when the server refuses without a reason of its own. */
const FALLBACK_ERROR = 'The closing time could not be saved. Try again in a moment.';

interface Draft {
  date: string;
  time: string;
}

/** Why the server refused the new time, in words. */
function refusal(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_ERROR;
  return error.fieldErrors.closes_at ?? error.message;
}

/**
 * The button, and once pressed, the date and time boxes with **Save closing time** and
 * **Cancel**.
 */
export function CloseTimeEditor({ callout }: { callout: CalloutDetail }): JSX.Element {
  const [draft, setDraft] = useState<Draft | null>(null);
  const move = useMoveCloseTime(callout.id);
  const toast = useToast();

  if (draft === null) {
    return (
      <div>
        <Button
          variant="secondary"
          onClick={() => {
            move.reset();
            setDraft(sitePartsOf(callout.closes_at));
          }}
        >
          Change closing time
        </Button>
      </div>
    );
  }

  // A time already chosen off the half hour stays on offer.
  const choices = TIME_CHOICES.some((choice) => choice.value === draft.time)
    ? TIME_CHOICES
    : [...TIME_CHOICES, timeChoice(draft.time)].sort((a, b) => a.value.localeCompare(b.value));

  const handleSubmit = (event: FormEvent): void => {
    event.preventDefault();
    const chosen = `${draft.date}T${draft.time}`;
    move.mutate(chosen, {
      onSuccess: () => {
        toast.show(`Answers now close ${chosenWords(chosen)}.`, 'success');
        setDraft(null);
      },
    });
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="stack-tight">
      <fieldset className="stack-tight">
        <legend className="field__label">Answers close</legend>
        <p className="field__hint">
          The buttons in the email keep working until then. The time is {SITE_TIME_ZONE_NAME}.
        </p>
        <div className="cluster">
          <Field label="Date">
            {(field) => (
              <input
                {...field}
                type="date"
                value={draft.date}
                onChange={(event) => setDraft({ ...draft, date: event.target.value })}
              />
            )}
          </Field>
          <Field label="Time">
            {(field) => (
              <select
                {...field}
                value={draft.time}
                onChange={(event) => setDraft({ ...draft, time: event.target.value })}
              >
                {choices.map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
      </fieldset>
      {move.isError ? (
        <p className="field__error" role="alert">
          {refusal(move.error)}
        </p>
      ) : null}
      <div className="cluster">
        <Button type="submit" disabled={move.isPending || draft.date === ''}>
          {move.isPending ? 'Saving…' : 'Save closing time'}
        </Button>
        <Button variant="quiet" onClick={() => setDraft(null)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
