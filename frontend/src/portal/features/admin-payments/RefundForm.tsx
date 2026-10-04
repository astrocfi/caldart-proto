/**
 * The refund form on a payment's detail screen.
 *
 * It opens with the whole unrefunded balance filled in, because a refund is
 * usually the whole thing, and with the membership term marked for cancellation
 * when the amount covers the dues the payment bought — a member who has their
 * money back has not paid for the year.
 */
import { useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { PaymentDetail, RefundReason } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { useToast } from '@/portal/components/Toast';
import { reportedErrors, unrefundedCents, useIssueRefund } from './api';
import { REFUND_REASON_LABELS } from './labels';

const REASONS: RefundReason[] = [
  'requested_by_member',
  'duplicate',
  'error',
  'fraudulent',
  'other',
];

export interface RefundFormProps {
  payment: PaymentDetail;
  /** Called once the refund has gone through. */
  onDone: () => void;
  onCancel: () => void;
}

/** Whether refunding `cents` should cancel the term the payment bought. */
export function shouldCancelTerm(payment: PaymentDetail, cents: number): boolean {
  if (payment.membership === null) return false;
  if (payment.plan_amount_cents === 0) return false;
  return cents >= payment.plan_amount_cents;
}

/** Dollars typed into the amount box as the integer cents the API takes. */
export function amountCents(typed: string): number {
  const dollars = Number(typed.trim());
  return Number.isFinite(dollars) ? Math.round(dollars * 100) : 0;
}

/** The refund form: an amount, a reason, a note, and whether the term goes with it. */
export function RefundForm({ payment, onDone, onCancel }: RefundFormProps): JSX.Element {
  const remaining = unrefundedCents(payment);
  const [amount, setAmount] = useState((remaining / 100).toFixed(2));
  const [reason, setReason] = useState<RefundReason>('requested_by_member');
  const [note, setNote] = useState('');
  const [cancelTerm, setCancelTerm] = useState(shouldCancelTerm(payment, remaining));
  // Once the treasurer has checked or unchecked the box themselves, the amount
  // stops speaking for them: it is their decision, not a running suggestion.
  const [hasChosenCancel, setHasChosenCancel] = useState(false);
  const refund = useIssueRefund(payment.id);
  // Read off the request itself, so the errors are on the page in the same render
  // that moves the focus to them.
  const errors: Record<string, string> =
    refund.error instanceof ApiError
      ? reportedErrors(refund.error)
      : refund.error
        ? { detail: "The refund wasn't recorded. Try again in a moment." }
        : {};
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, refund.error);
  // What the server said about a field goes once the field is edited.
  const shown = useFreshErrors(
    refund.error,
    { amount_cents: amount, reason, note, cancel_term: cancelTerm },
    errors,
  );

  function handleAmountChange(typed: string) {
    setAmount(typed);
    if (!hasChosenCancel) setCancelTerm(shouldCancelTerm(payment, amountCents(typed)));
  }

  function handleCancelTermChange(checked: boolean) {
    setHasChosenCancel(true);
    setCancelTerm(checked);
  }

  function handleCancel() {
    onCancel();
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    refund.mutate(
      {
        amount_cents: amountCents(amount),
        reason,
        note,
        cancel_term: cancelTerm,
      },
      {
        onSuccess: (issued) => {
          toast.show(`Refunded ${formatCents(issued.refund.amount_cents)}.`, 'success');
          onDone();
        },
      },
    );
  }

  return (
    <form
      ref={formRef}
      className="stack refund-form"
      onSubmit={handleSubmit}
      aria-labelledby="refund-form"
    >
      <h3 id="refund-form">Refund this payment</h3>
      <p className="muted">{formatCents(remaining)} of this payment is left to refund.</p>

      <Field label="Amount" hint="In US dollars." error={shown.amount_cents} required>
        {(props) => (
          <input
            {...props}
            type="number"
            min="0"
            step="0.01"
            value={amount}
            onChange={(event) => handleAmountChange(event.target.value)}
          />
        )}
      </Field>

      <Field label="Reason" error={shown.reason} required>
        {(props) => (
          <select
            {...props}
            value={reason}
            onChange={(event) => setReason(event.target.value as RefundReason)}
          >
            {REASONS.map((option) => (
              <option key={option} value={option}>
                {REFUND_REASON_LABELS[option]}
              </option>
            ))}
          </select>
        )}
      </Field>

      <Field
        label="Note"
        hint="Kept with the refund; the member does not see it"
        error={shown.note}
      >
        {(props) => (
          <input
            {...props}
            type="text"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        )}
      </Field>

      {payment.membership === null ? null : (
        <label className="checkbox">
          <input
            type="checkbox"
            checked={cancelTerm}
            onChange={(event) => handleCancelTermChange(event.target.checked)}
          />
          Cancel the membership term this payment bought
        </label>
      )}

      {shown.detail ? (
        <p className="field__error" role="alert">
          {shown.detail}
        </p>
      ) : null}

      <div className="cluster">
        <Button type="submit" variant="danger" disabled={refund.isPending}>
          {refund.isPending ? 'Refunding…' : 'Refund'}
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
        <RefusedSubmitNote count={refusal.count} />
      </div>
    </form>
  );
}
