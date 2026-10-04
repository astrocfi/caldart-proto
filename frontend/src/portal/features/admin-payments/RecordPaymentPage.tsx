/**
 * `/admin/payments/record` — money that arrived by check, cash or transfer.
 *
 * The member is found by typing, as on the member list, because a treasurer
 * has a check in their hand and a name on it rather than an id.  Everything
 * else is the same decision a card checkout makes: which plan, how much of it
 * is a gift, and when the money arrived.
 */
import { useEffect, useRef, useState } from 'react';
import type { FormEvent, JSX, RefObject } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { usePlans } from '@/portal/api/queries';
import type { FinanceMember, ManualMethod, Plan } from '@/portal/api/types';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { todayIso } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { MembershipDot, membershipWord } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { Typeahead } from '@/portal/components/Typeahead';
import { reportedErrors, useFinanceMemberSearch, useRecordPayment } from './api';
import { FinanceTabs } from './FinanceTabs';
import { MANUAL_METHOD_LABELS } from './labels';
import './admin-payments.css';

const METHODS: ManualMethod[] = ['check', 'cash', 'bank_transfer', 'other'];

/** The id of the line that sums what the form will record. */
const TOTAL_ID = 'record-payment-total';

/** The fewest characters of a name or address worth searching for. */
const MEMBER_SEARCH_MIN_LENGTH = 2;

/** Dollars typed into a money box as the integer cents the API takes. */
export function contributionCents(typed: string): number {
  const dollars = Number(typed.trim());
  if (!Number.isFinite(dollars) || dollars < 0) return 0;
  return Math.round(dollars * 100);
}

/**
 * What the form will record, as the treasurer checks it against the check in their
 * hand: `Dues $45.00 + contribution $0.00 = $45.00`.  No plan is dues of nothing.
 */
export function recordedSum(plan: Plan | undefined, contribution: number): string {
  const dues = plan?.price_cents ?? 0;
  return `Dues ${formatCents(dues)} + contribution ${formatCents(contribution)} = ${formatCents(dues + contribution)}`;
}

/** Where the payment page is told it was reached by recording the payment. */
export interface RecordedState {
  recorded: true;
}

interface MemberPickerProps {
  chosen: FinanceMember | null;
  onChoose: (member: FinanceMember | null) => void;
  error?: string;
  /** Holds the search box, which takes the focus back after **Choose somebody else**. */
  pickerRef: RefObject<HTMLDivElement | null>;
}

/**
 * The member search, the shared `Typeahead`, or the member chosen from it with the way
 * to choose again.  Each match names the person's address and membership state.
 */
function MemberPicker({ chosen, onChoose, error, pickerRef }: MemberPickerProps): JSX.Element {
  const [term, setTerm] = useState('');

  if (chosen !== null) {
    return (
      <div className="record-payment__chosen">
        <p>
          <strong>{chosen.name}</strong> <span className="muted">{chosen.email}</span>{' '}
          <MembershipDot membership={chosen.membership} />
        </p>
        <Button variant="quiet" small onClick={() => onChoose(null)}>
          Choose somebody else
        </Button>
      </div>
    );
  }

  return (
    <div ref={pickerRef}>
      <Field
        label="Member"
        hint="Type part of a name or an email address, then choose the person."
        error={error}
        required
      >
        {(props) => (
          <Typeahead
            {...props}
            listLabel="Matching members"
            placeholder="Name or email address"
            autoComplete="off"
            value={term}
            minLength={MEMBER_SEARCH_MIN_LENGTH}
            onValueChange={setTerm}
            onPick={onChoose}
            useSuggestions={useFinanceMemberSearch}
            itemKey={(member) => String(member.user_id)}
            itemLabel={(member) => member.name}
            itemMeta={(member) => `${member.email} · ${membershipWord(member.membership)}`}
          />
        )}
      </Field>
    </div>
  );
}

/** `/admin/payments/record`: the form behind a check, some cash or a transfer. */
export function RecordPaymentPage(): JSX.Element {
  const [member, setMember] = useState<FinanceMember | null>(null);
  const [plan, setPlan] = useState('');
  const [contribution, setContribution] = useState('0.00');
  const [method, setMethod] = useState<ManualMethod>('check');
  const [reference, setReference] = useState('');
  const [receivedOn, setReceivedOn] = useState(todayIso());
  const [note, setNote] = useState('');
  const [memberError, setMemberError] = useState<string | null>(null);

  const plans = usePlans();
  const chosenPlan = plans.data?.find((option) => option.slug === plan);
  const record = useRecordPayment();
  const toast = useToast();
  const navigate = useNavigate();
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, record.error);
  const pickerRef = useRef<HTMLDivElement>(null);
  const planRef = useRef<HTMLSelectElement>(null);
  // Picking a member moves on to the plan; choosing again goes back to the search.
  const [hasPicked, setHasPicked] = useState(false);

  // Read off the request itself, so the errors are on the page in the same render
  // that moves the focus to them; a field's error goes once the field is edited.
  const serverErrors = useFreshErrors(
    record.error,
    {
      user_id: member,
      plan,
      contribution_cents: contribution,
      amount_cents: contribution,
      method,
      reference,
      received_on: receivedOn,
      note,
    },
    record.error instanceof ApiError
      ? reportedErrors(record.error)
      : record.error
        ? { detail: "The payment wasn't recorded. Try again in a moment." }
        : {},
  );
  const errors: Record<string, string | undefined> =
    memberError === null ? serverErrors : { ...serverErrors, user_id: memberError };

  useEffect(() => {
    if (!hasPicked) return;
    if (member === null) pickerRef.current?.querySelector('input')?.focus();
    else planRef.current?.focus();
  }, [hasPicked, member]);

  function handleChooseMember(chosen: FinanceMember | null) {
    setMember(chosen);
    setMemberError(null);
    setHasPicked(true);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    // Enter in the member search picks a match or does nothing; it never sends the form.
    if (member === null && pickerRef.current?.contains(document.activeElement) === true) return;
    if (member === null) {
      setMemberError('Choose the member this payment is for.');
      refusal.refuse();
      return;
    }
    setMemberError(null);
    record.mutate(
      {
        user_id: member.user_id,
        plan: plan === '' ? null : plan,
        contribution_cents: contributionCents(contribution),
        method,
        reference,
        received_on: receivedOn,
        note,
      },
      {
        onSuccess: (payment) => {
          toast.show(`Recorded ${payment.receipt_number}.`, 'success');
          const state: RecordedState = { recorded: true };
          void navigate(`/admin/payments/${payment.id}`, { state });
        },
      },
    );
  }

  return (
    <Page
      title="Record a payment"
      lede="Record a check, cash, or a bank transfer. The membership starts and the member is emailed a receipt."
    >
      <FinanceTabs current="/admin/payments/list" />

      <Card>
        <form ref={formRef} className="stack finance-form" onSubmit={handleSubmit} noValidate>
          <MemberPicker
            chosen={member}
            onChoose={handleChooseMember}
            error={errors.user_id}
            pickerRef={pickerRef}
          />

          <Field
            label="Plan"
            hint="Choose No membership to record a contribution on its own."
            error={errors.plan}
          >
            {(props) => (
              <select
                {...props}
                ref={planRef}
                value={plan}
                onChange={(event) => setPlan(event.target.value)}
              >
                <option value="">No membership</option>
                {(plans.data ?? []).map((option) => (
                  <option key={option.slug} value={option.slug}>
                    {option.name}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field label="Contribution" error={errors.contribution_cents ?? errors.amount_cents}>
            {(props) => (
              <span className="money-input">
                <span aria-hidden="true">$</span>
                <input
                  {...props}
                  type="number"
                  min="0"
                  step="0.01"
                  className="num"
                  value={contribution}
                  onChange={(event) => setContribution(event.target.value)}
                />
              </span>
            )}
          </Field>

          <Field label="Method" error={errors.method} required>
            {(props) => (
              <select
                {...props}
                value={method}
                onChange={(event) => setMethod(event.target.value as ManualMethod)}
              >
                {METHODS.map((option) => (
                  <option key={option} value={option}>
                    {MANUAL_METHOD_LABELS[option]}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field
            label="Reference"
            hint="Check number or bank transfer reference"
            error={errors.reference}
          >
            {(props) => (
              <input
                {...props}
                type="text"
                value={reference}
                onChange={(event) => setReference(event.target.value)}
              />
            )}
          </Field>

          <Field label="Received on" error={errors.received_on} required>
            {(props) => (
              <input
                {...props}
                type="date"
                value={receivedOn}
                onChange={(event) => setReceivedOn(event.target.value)}
              />
            )}
          </Field>

          <Field label="Note" error={errors.note}>
            {(props) => (
              <input
                {...props}
                type="text"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            )}
          </Field>

          {errors.detail || errors.non_field_errors ? (
            <p className="field__error" role="alert">
              {errors.detail ?? errors.non_field_errors}
            </p>
          ) : null}

          {/* Described by the sum, so the button is heard with what it will record. */}
          <p className="record-payment__total" id={TOTAL_ID}>
            {recordedSum(chosenPlan, contributionCents(contribution))}
          </p>

          <div className="cluster">
            <Button type="submit" disabled={record.isPending} aria-describedby={TOTAL_ID}>
              {record.isPending ? 'Recording…' : 'Record the payment'}
            </Button>
            <RefusedSubmitNote count={refusal.count} />
            <ButtonLink to="/admin/payments/list" variant="quiet">
              Cancel
            </ButtonLink>
          </div>
        </form>
      </Card>
    </Page>
  );
}
