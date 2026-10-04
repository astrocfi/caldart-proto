/**
 * The mission callout choice in **What it says**: the switch that makes the email a
 * callout, and when its answers close.
 *
 * A callout's copies each carry three buttons, Available, Available with limits, and
 * Not available, and the answers collect on the Callouts screen. Turning the switch
 * on makes the email Mission email when the sender may send that kind, and sets the
 * answers to close two days ahead; both can be changed. Every change saves at once,
 * as the type does. Once the email has started sending the choice is shown, not
 * changed.
 */
import { useId, useState } from 'react';
import type { JSX } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/portal/api/client';
import { Field } from '@/portal/components/Field';
import { batchKey, useUpdateBulkEmail } from './api';
import {
  SITE_TIME_ZONE_NAME,
  TIME_CHOICES,
  scheduledWords,
  sitePartsOf,
  timeChoice,
} from './schedule';

/** What the switch says a callout does. */
export const CALLOUT_HINT =
  'Each copy carries three buttons, Available, Available with limits, and Not available. ' +
  'The answers collect on the Callouts screen.';

/** What the time boxes say when the server refuses a time without a reason of its own. */
const FALLBACK_ERROR = 'The time answers close could not be saved. Try again in a moment.';

interface CalloutFieldsProps {
  emailId: number;
  isCallout: boolean;
  /** When the answers close, as the server holds it; null for an ordinary email. */
  closesAt: string | null;
  isEditable: boolean;
}

/** Why the server refused a change, in words. */
function refusal(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_ERROR;
  return error.fieldErrors.closes_at ?? error.message;
}

/** The callout switch, and the date and time its answers close. */
export function CalloutFields({
  emailId,
  isCallout,
  closesAt,
  isEditable,
}: CalloutFieldsProps): JSX.Element | null {
  const update = useUpdateBulkEmail(emailId);
  const queryClient = useQueryClient();
  const hintId = useId();

  if (!isEditable) {
    if (!isCallout) return null;
    return (
      <p>
        <strong>Mission callout:</strong> answers close {scheduledWords(closesAt)}.
      </p>
    );
  }

  const handleToggle = (checked: boolean): void => {
    update.mutate(
      { is_callout: checked },
      // The type may become Mission, which changes who the batch skips.
      { onSuccess: () => void queryClient.invalidateQueries({ queryKey: batchKey(emailId) }) },
    );
  };

  return (
    <div className="stack-tight bulk-email__callout">
      <div className="bulk-email__type">
        <input
          id={`${hintId}-switch`}
          type="checkbox"
          role="switch"
          checked={isCallout}
          aria-describedby={hintId}
          onChange={(event) => handleToggle(event.target.checked)}
        />
        <div>
          <label htmlFor={`${hintId}-switch`} className="bulk-email__type-name">
            This is a mission callout
          </label>
          <p id={hintId} className="muted bulk-email__type-description">
            {CALLOUT_HINT}
          </p>
        </div>
      </div>
      {isCallout && closesAt !== null ? (
        <ClosesAtFields
          key={closesAt}
          closesAt={closesAt}
          error={update.isError ? refusal(update.error) : null}
          onChoose={(chosen) => update.mutate({ closes_at: chosen })}
        />
      ) : null}
      {!update.isError || isCallout ? null : (
        <p className="field__error" role="alert">
          {refusal(update.error)}
        </p>
      )}
    </div>
  );
}

interface ClosesAtFieldsProps {
  closesAt: string;
  error: string | null;
  /** Called with the chosen close time as `YYYY-MM-DDTHH:MM` in the site's time zone. */
  onChoose: (closesAt: string) => void;
}

/** The date and the time the answers close, each saving the moment it changes. */
function ClosesAtFields({
  closesAt,
  error,
  onChoose: handleChoose,
}: ClosesAtFieldsProps): JSX.Element {
  const saved = sitePartsOf(closesAt);
  const [date, setDate] = useState(saved.date);
  const [time, setTime] = useState(saved.time);
  // A time already chosen off the half hour stays on offer.
  const choices = TIME_CHOICES.some((choice) => choice.value === time)
    ? TIME_CHOICES
    : [...TIME_CHOICES, timeChoice(time)].sort((a, b) => a.value.localeCompare(b.value));

  return (
    <fieldset className="bulk-email__fieldset stack-tight">
      <legend className="field__label">Answers close</legend>
      <p className="field__hint">
        After this, the buttons in the email record nothing. The time is {SITE_TIME_ZONE_NAME}.
      </p>
      <div className="cluster bulk-email__schedule">
        <Field label="Date">
          {(field) => (
            <input
              {...field}
              type="date"
              value={date}
              onChange={(event) => {
                setDate(event.target.value);
                if (event.target.value !== '') handleChoose(`${event.target.value}T${time}`);
              }}
            />
          )}
        </Field>
        <Field label="Time">
          {(field) => (
            <select
              {...field}
              value={time}
              onChange={(event) => {
                setTime(event.target.value);
                handleChoose(`${date}T${event.target.value}`);
              }}
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
      {error === null ? null : (
        <p className="field__error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
