/**
 * **Settle** on a renewal charge held in doubt: the payment provider may have taken
 * it and cannot say, so the automatic run doesn't charge it again until a treasurer
 * has looked in the provider's own dashboard.
 *
 * The panel names what to search the dashboard for -- the charge's invoice id, its
 * amount, and when it was sent -- and takes the treasurer's answer: **Record as
 * paid** with the provider's capture id, which renews the member's term and emails
 * them as any charge does; or, once the treasurer has checked that they didn't find
 * a payment, **No payment found**, which lets the next run charge it again, or **Close
 * as failed**, which doesn't charge it, pauses the member's automatic renewal or
 * recurring donation if it is on, and emails them that it is paused. The panel asks the
 * treasurer to get in touch with the member too, and hands the answer to a closed
 * charge, which carries the member's phone number and address, to `onClosed`.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalAttempt, RenewalSettleOutcome, RenewalSettleResult } from '@/portal/api/types';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { DateText } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Money } from '@/portal/components/Money';
import { useToast } from '@/portal/components/Toast';
import { MANDATE_KIND_LABELS } from './labels';
import { useSettleAttempt } from './reports-api';

export interface SettleChargeButtonProps {
  attempt: RenewalAttempt;
  /** Called with the settle call's answer once the charge is closed as failed. */
  onClosed: (result: RenewalSettleResult) => void;
}

/** The id a renewal charge's order carries at PayPal, to search its dashboard for. */
export function renewalInvoiceId(paymentId: number): string {
  return `caldart-renewal-${paymentId}`;
}

/** Records a charge held in doubt as paid, releases it, or closes it as failed. */
export function SettleChargeButton({ attempt, onClosed }: SettleChargeButtonProps): JSX.Element {
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
  const answer = (
    outcome: RenewalSettleOutcome,
    handleDone: (result: RenewalSettleResult) => void,
  ): Promise<unknown> =>
    settle
      .mutateAsync({
        attemptId: attempt.id,
        body: outcome === 'paid' ? { outcome, reference: reference.trim() } : { outcome },
      })
      .then(handleDone, (error: unknown) => {
        toast.show(
          error instanceof Error ? error.message : 'That charge could not be settled.',
          'error',
        );
        throw error;
      });

  const confirm = (message: string): void => toast.show(message, 'success');

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
          onChoose: () => answer('paid', () => confirm(`The charge for ${name} is recorded.`)),
        },
        {
          label: 'No payment found',
          disabled: !isNothingFound,
          onChoose: () =>
            answer('released', () =>
              confirm(`The charge for ${name} will be taken on the next run.`),
            ),
        },
        {
          label: 'Close as failed',
          variant: 'danger',
          disabled: !isNothingFound,
          // The page reports a closed charge, keeping the member's phone and address on screen.
          onChoose: () => answer('failed', onClosed),
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
        searched the dashboard and didn&rsquo;t find a payment for this invoice
      </label>
      <p className="muted">
        No payment found lets the next run charge it again. Close as failed doesn&rsquo;t charge it
        again, pauses {name}&rsquo;s {MANDATE_KIND_LABELS[attempt.mandate_kind].toLowerCase()} if it
        is on, and emails them that it is paused; please get in touch with them too. Either needs
        the search confirmed.
      </p>
    </ConfirmButton>
  );
}
