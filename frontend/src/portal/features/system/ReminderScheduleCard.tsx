/**
 * The **Reminder schedule** card: how many days before expiry the first, second, and final
 * renewal reminders go, and how many days after it the lapsed one does.
 *
 * A system administrator edits the four days in place on the Scheduled page; an account
 * administrator reads the same schedule on the Reminders page, without the form.
 */
import { useState } from 'react';
import type { ChangeEvent, FormEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { ReminderSchedule, ReminderSchedulePayload } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { useReminderSchedule, useSaveReminderSchedule } from './api';
import { days, SCHEDULE_FIELDS } from './reminderSchedule';
import './reminderSchedule.css';

const TITLE = 'Reminder schedule';
const EYEBROW = 'Membership';

/** The form's values: each day field as typed. */
type Draft = Record<keyof ReminderSchedulePayload, string>;

/** What a field left empty reads, without asking the server. */
const BLANK_MESSAGE = 'Enter a number of days.';

interface ReminderScheduleCardProps {
  /** Show the schedule without the form, for a reader who cannot change it. */
  readOnly?: boolean;
}

/** The reminder schedule, editable unless `readOnly`. */
export function ReminderScheduleCard({ readOnly = false }: ReminderScheduleCardProps): JSX.Element {
  const schedule = useReminderSchedule();

  if (schedule.isPending) {
    return (
      <Card eyebrow={EYEBROW} title={TITLE}>
        <p className="muted" role="status">
          Loading the reminder schedule…
        </p>
      </Card>
    );
  }

  if (schedule.isError) {
    return (
      <Card eyebrow={EYEBROW} title={TITLE}>
        <p className="muted">The reminder schedule could not be loaded.</p>
      </Card>
    );
  }

  return (
    <Card eyebrow={EYEBROW} title={TITLE}>
      {readOnly ? (
        <ScheduleFacts stored={schedule.data} />
      ) : (
        // Keyed by the save time, so a save from elsewhere resets the form to what is stored.
        <ScheduleForm key={schedule.data.updated_at ?? 'defaults'} stored={schedule.data} />
      )}
      <p className="muted">{storedLine(schedule.data)}</p>
    </Card>
  );
}

/** Who saved the schedule last and when, or that the defaults apply. */
function storedLine({ updated_at: updatedAt, updated_by: updatedBy }: ReminderSchedule): string {
  if (updatedAt === null) return 'The default schedule: nobody has changed it.';
  const date = formatDate(updatedAt);
  return updatedBy === null ? `Last saved ${date}` : `Last saved ${date} by ${updatedBy}`;
}

interface StoredProps {
  stored: ReminderSchedule;
}

/** The schedule as four labeled lines. */
function ScheduleFacts({ stored }: StoredProps): JSX.Element {
  return (
    <dl className="reminder-schedule__facts">
      {SCHEDULE_FIELDS.map(({ name, label, side }) => (
        <div key={name}>
          <dt>{label}</dt>
          <dd>{`${days(stored[name])} ${side} expiry`}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The schedule's four day fields and Save. */
function ScheduleForm({ stored }: StoredProps): JSX.Element {
  const [draft, setDraft] = useState<Draft>(() => draftOf(stored));
  const [blankErrors, setBlankErrors] = useState<Record<string, string>>({});
  const save = useSaveReminderSchedule();
  const toast = useToast();
  const serverErrors = save.error instanceof ApiError ? save.error.fieldErrors : {};
  const errors = { ...serverErrors, ...blankErrors };

  const handleChange =
    (name: keyof ReminderSchedulePayload) =>
    (event: ChangeEvent<HTMLInputElement>): void => {
      const { value } = event.target;
      setDraft((current) => ({ ...current, [name]: value }));
    };

  const handleSubmit = (event: FormEvent): void => {
    event.preventDefault();
    const blanks = blankErrorsOf(draft);
    setBlankErrors(blanks);
    if (Object.keys(blanks).length > 0) return;
    save.mutate(payloadOf(draft), {
      onSuccess: () => toast.show('Reminder schedule saved.', 'success'),
    });
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="stack">
      <p className="muted">
        The expired reminder goes from the day a membership ends through the six days after, and has
        no number. A change applies from the next morning&rsquo;s scan, and never sends a member a
        reminder they already had.
      </p>
      <div className="reminder-schedule__fields">
        {SCHEDULE_FIELDS.map(({ name, label, side, min, max }) => (
          <Field key={name} label={label} hint={`Days ${side} expiry`} error={errors[name]}>
            {(field) => (
              <input
                {...field}
                type="number"
                inputMode="numeric"
                min={min}
                max={max}
                className="num"
                value={draft[name]}
                onChange={handleChange(name)}
              />
            )}
          </Field>
        ))}
      </div>
      <div className="cluster">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </form>
  );
}

/** The stored days as the form's text values. */
function draftOf(stored: ReminderSchedulePayload): Draft {
  return {
    first_days_before: String(stored.first_days_before),
    second_days_before: String(stored.second_days_before),
    final_days_before: String(stored.final_days_before),
    lapsed_days_after: String(stored.lapsed_days_after),
  };
}

/** `BLANK_MESSAGE` for every field left empty, keyed by field. */
function blankErrorsOf(draft: Draft): Record<string, string> {
  return Object.fromEntries(
    SCHEDULE_FIELDS.filter(({ name }) => draft[name].trim() === '').map(({ name }) => [
      name,
      BLANK_MESSAGE,
    ]),
  );
}

/** The form's values as the `PUT` body, once `blankErrorsOf` has found no field empty. */
function payloadOf(draft: Draft): ReminderSchedulePayload {
  return {
    first_days_before: Number(draft.first_days_before),
    second_days_before: Number(draft.second_days_before),
    final_days_before: Number(draft.final_days_before),
    lapsed_days_after: Number(draft.lapsed_days_after),
  };
}
