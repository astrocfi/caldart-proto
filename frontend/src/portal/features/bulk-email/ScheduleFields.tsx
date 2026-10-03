/**
 * Schedule for later: a date and a time in the site's time zone, then on to the
 * confirmation. The server refuses a time in the past or more than a year ahead,
 * and the card shows its sentence.
 *
 * The focus starts in the date box, and the Escape key goes back, as **Go back**
 * does.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, KeyboardEvent } from 'react';

import { Button } from '@/portal/components/Button';
import { todayIso } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { SITE_TIME_ZONE_NAME, TIME_CHOICES, timeChoice } from './schedule';

/** The time a schedule offers first: a morning newsletter. */
const DEFAULT_TIME = '08:00';

/** Tomorrow on the reader's clock, as `YYYY-MM-DD`. */
function tomorrowIso(today: Date = new Date()): string {
  const next = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  return todayIso(next);
}

interface ScheduleFieldsProps {
  /** The date and time to start from, such as the time already chosen; tomorrow at 8 otherwise. */
  initial?: { date: string; time: string };
  /** Called with the chosen start as `YYYY-MM-DDTHH:MM`. */
  onChoose: (startAt: string) => void;
  onBack: () => void;
}

/** The date and time boxes, with Continue and Go back. */
export function ScheduleFields({
  initial,
  onChoose: handleChoose,
  onBack: handleBack,
}: ScheduleFieldsProps): JSX.Element {
  const [date, setDate] = useState(() => initial?.date ?? tomorrowIso());
  const [time, setTime] = useState(() => initial?.time ?? DEFAULT_TIME);
  const dateRef = useRef<HTMLInputElement>(null);
  const isComplete = date !== '' && time !== '';
  // A time already chosen off the half hour stays on offer.
  const choices = TIME_CHOICES.some((choice) => choice.value === time)
    ? TIME_CHOICES
    : [...TIME_CHOICES, timeChoice(time)].sort((a, b) => a.value.localeCompare(b.value));

  useEffect(() => {
    dateRef.current?.focus();
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>): void => {
    if (event.key !== 'Escape') return;
    event.stopPropagation();
    handleBack();
  };

  return (
    <section className="stack-tight" aria-label="Schedule for later">
      <p>Choose when it should go out. The time is {SITE_TIME_ZONE_NAME}.</p>
      <div className="cluster bulk-email__schedule">
        <Field label="Date">
          {(field) => (
            <input
              {...field}
              ref={dateRef}
              type="date"
              min={todayIso()}
              value={date}
              onChange={(event) => setDate(event.target.value)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
        <Field label="Time">
          {(field) => (
            <select
              {...field}
              value={time}
              onChange={(event) => setTime(event.target.value)}
              onKeyDown={handleKeyDown}
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
      <div className="cluster">
        <Button
          onClick={() => handleChoose(`${date}T${time}`)}
          onKeyDown={handleKeyDown}
          disabled={!isComplete}
        >
          Continue
        </Button>
        <Button variant="quiet" onClick={handleBack} onKeyDown={handleKeyDown}>
          Go back
        </Button>
      </div>
    </section>
  );
}
