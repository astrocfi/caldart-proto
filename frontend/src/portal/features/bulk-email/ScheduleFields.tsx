/**
 * Schedule for later: a date and a time in the site's time zone, then on to the
 * confirmation. The server refuses a time in the past or more than a year ahead,
 * and the card shows its sentence.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { todayIso } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { SITE_TIME_ZONE_NAME } from './SendConfirm';

/** The time a schedule offers first: a morning newsletter. */
const DEFAULT_TIME = '08:00';

/** Tomorrow on the reader's clock, as `YYYY-MM-DD`. */
function tomorrowIso(today: Date = new Date()): string {
  const next = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  return todayIso(next);
}

interface ScheduleFieldsProps {
  /** Called with the chosen start as `YYYY-MM-DDTHH:MM`. */
  onChoose: (startAt: string) => void;
  onBack: () => void;
}

/** The date and time boxes, with Continue and Go back. */
export function ScheduleFields({
  onChoose: handleChoose,
  onBack: handleBack,
}: ScheduleFieldsProps): JSX.Element {
  const [date, setDate] = useState(tomorrowIso);
  const [time, setTime] = useState(DEFAULT_TIME);
  const isComplete = date !== '' && time !== '';

  return (
    <section className="stack-tight" aria-label="Schedule for later">
      <p>Choose when it should go out. The time is {SITE_TIME_ZONE_NAME}.</p>
      <div className="cluster bulk-email__schedule">
        <Field label="Date">
          {(field) => (
            <input
              {...field}
              type="date"
              min={todayIso()}
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          )}
        </Field>
        <Field label="Time">
          {(field) => (
            <input
              {...field}
              type="time"
              value={time}
              onChange={(event) => setTime(event.target.value)}
            />
          )}
        </Field>
      </div>
      <div className="cluster">
        <Button onClick={() => handleChoose(`${date}T${time}`)} disabled={!isComplete}>
          Continue
        </Button>
        <Button variant="quiet" onClick={handleBack}>
          Go back
        </Button>
      </div>
    </section>
  );
}
