/**
 * **Settle** on a renewal charge held in doubt: the payment provider may have taken
 * it and cannot say, so the automatic run charges nothing more until a treasurer has
 * looked in the provider's own dashboard.
 *
 * The panel names what to search the dashboard for -- the charge's invoice id, its
 * amount, and when it was sent -- and takes the treasurer's answer: **Record as
 * paid** with the provider's capture id, which renews the member's term and emails
 * them as any charge does; or, once the treasurer has checked that they found no
 * charge, **It took nothing**, which lets the next run charge it again, or **Close
 * as failed**, which charges nothing and pauses the member's automatic renewal.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalAttempt, RenewalSettleOutcome } from '@/portal/api/types';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { DateText } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Money } from '@/portal/components/Money';
import { useToast } from '@/portal/components/Toast';
import { useSettleAttempt } from './reports-api';

export interface SettleChargeButtonProps {
  attempt: RenewalAttempt;
}

/** The id a renewal charge's order carries at PayPal, to search its dashboard for. */
export function renewalInvoiceId(paymentId: number): string {
  return `caldart-renewal-${paymentId}`;
}

/** Records a charge held in doubt as paid, releases it, or closes it as failed. */
export function SettleChargeButton({ attempt }: SettleChargeButtonProps): JSX.Element {
  const [reference, setReference] = useState('');
  const [isNothingFound, setIsNothingFound] = useState(false);
  const settle = useSettleAttempt();
  const toast = useToast();

  const handleReferenceChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setReference(event.target.value);
  };

  const handleNothingFoundChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setIsNothingFound(event.target.checked);
  };

  // Rejects when the request fails, so the panel stays open with the answer still in it.
  const answer = (outcome: RenewalSettleOutcome, done: string): Promise<unknown> =>
    settle
      .mutateAsync({
        attemptId: attempt.id,
        body: outcome === 'paid' ? { outcome, reference: reference.trim() } : { outcome },
      })
      .then(
        () => toast.show(done, 'success'),
        (error: unknown) => {
          toast.show(
            error instanceof Error ? error.message : 'That charge could not be settled.',
            'error',
          );
          throw error;
        },
      );

  const name = attempt.user_name;
  return (
    <ConfirmButton
      label="Settle"
      name={`Settle the charge for ${name}`}
      variant="quiet"
      small
      choices={[
        {
          label: 'Record as paid',
          disabled: reference.trim() === '',
          onChoose: () => answer('paid', `The charge for ${name} is recorded.`),
        },
        {
          label: 'It took nothing',
          disabled: !isNothingFound,
          onChoose: () =>
            answer('released', `The charge for ${name} will be taken on the next run.`),
        },
        {
          label: 'Close as failed',
          variant: 'danger',
          disabled: !isNothingFound,
          onChoose: () =>
            answer('failed', `The charge for ${name} is closed and their renewal is paused.`),
        },
      ]}
    >
      <p>
        Search the payment provider&rsquo;s dashboard for this charge.
        {attempt.payment_id === null ? null : (
          <>
            {' '}
            Its invoice id is <code>{renewalInvoiceId(attempt.payment_id)}</code>
          </>
        )}
        {attempt.payment_amount_cents === null ? null : (
          <>
            , for <Money cents={attempt.payment_amount_cents} />
          </>
        )}
        {attempt.payment_sent_at === null ? null : (
          <>
            , sent <DateText value={attempt.payment_sent_at} withTime />
          </>
        )}
        .
      </p>
      <Field label="Capture ID">
        {(props) => (
          <input {...props} type="text" value={reference} onChange={handleReferenceChange} />
        )}
      </Field>
      <label className="cluster">
        <input type="checkbox" checked={isNothingFound} onChange={handleNothingFoundChange} />I
        searched the dashboard and it holds no charge for this invoice
      </label>
      <p className="muted">
        It took nothing lets the next run charge it again; Close as failed charges nothing more and
        pauses {name}&rsquo;s automatic renewal. Either needs the search confirmed.
      </p>
    </ConfirmButton>
  );
}
