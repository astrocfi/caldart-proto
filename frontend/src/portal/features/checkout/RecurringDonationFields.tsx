/**
 * The block under the amount that makes a contribution a recurring donation.
 *
 * A checkbox, then -- once it is ticked -- how often, and the day of the first
 * charge, which opens on today and never offers a day before it.  The line under
 * them says what will happen in money and dates, so nobody ticks a box without
 * knowing what it does.
 */
import { useId } from 'react';
import type { JSX } from 'react';

import type { IsoDate, MandateCadence } from '@/portal/api/types';
import { formatDate, todayIso } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import { CADENCE_PHRASES } from '@/portal/features/payments/labels';
import { CadenceChooser } from './CadenceChooser';

export interface RecurringDonation {
  isRecurring: boolean;
  cadence: MandateCadence;
  firstChargeOn: IsoDate;
}

export interface RecurringDonationFieldsProps {
  value: RecurringDonation;
  onChange: (next: RecurringDonation) => void;
  /** What each charge comes to, in cents. */
  amountCents: number;
}

/** The recurring-donation checkbox, cadence radios, and first-charge day. */
export function RecurringDonationFields({
  value,
  onChange,
  amountCents,
}: RecurringDonationFieldsProps): JSX.Element {
  const checkboxId = useId();
  const today = todayIso();

  return (
    <div className="checkout__auto-renew checkout__recurring">
      <label className="checkout__auto-renew-label" htmlFor={checkboxId}>
        <input
          id={checkboxId}
          type="checkbox"
          checked={value.isRecurring}
          onChange={(event) => onChange({ ...value, isRecurring: event.target.checked })}
        />
        <span>Make this a recurring donation</span>
      </label>

      {value.isRecurring ? (
        <>
          <CadenceChooser
            value={value.cadence}
            onChange={(cadence) => onChange({ ...value, cadence })}
          />
          <Field label="First charge on">
            {(props) => (
              <input
                {...props}
                type="date"
                required
                min={today}
                value={value.firstChargeOn}
                onChange={(event) => onChange({ ...value, firstChargeOn: event.target.value })}
              />
            )}
          </Field>
          {value.firstChargeOn === '' ? null : (
            <p className="checkout__fineprint muted">
              {recurringSummary(value, amountCents, today)}
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}

/**
 * What a recurring donation will do, in one or two sentences.
 *
 * A first charge today is taken now; a later one is taken on its day with
 * nothing charged today.  A yearly donation is announced a fortnight ahead of
 * every charge, and a monthly or quarterly one is not.
 */
export function recurringSummary(
  { cadence, firstChargeOn }: RecurringDonation,
  amountCents: number,
  today: IsoDate,
): string {
  const amount = formatCents(amountCents);
  const phrase = CADENCE_PHRASES[cadence];
  const when =
    firstChargeOn > today
      ? `Nothing is charged today. CalDART will charge ${amount} on ${formatDate(firstChargeOn)}, and ${phrase} after that.`
      : `CalDART charges ${amount} today, and ${phrase} after that.`;
  const notice =
    cadence === 'yearly'
      ? 'We will email you fourteen days before every charge.'
      : 'We email you a receipt after every charge.';
  return `${when} ${notice} You can change it or turn it off at any time from Payments.`;
}
