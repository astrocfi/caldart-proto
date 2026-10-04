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
import type { FinanceMember, ManualMethod } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { todayIso } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { MembershipDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { useDebounced } from '@/portal/components/useDebounced';
import { reportedErrors, useFinanceMemberSearch, useRecordPayment } from './api';
import { FinanceTabs } from './FinanceTabs';
import { MANUAL_METHOD_LABELS } from './labels';
import './admin-payments.css';

const METHODS: ManualMethod[] = ['check', 'cash', 'bank_transfer', 'other'];

/** Dollars typed into a money box as the integer cents the API takes. */
export function contributionCents(typed: string): number {
  const dollars = Number(typed.trim());
  if (!Number.isFinite(dollars) || dollars < 0) return 0;
  return Math.round(dollars * 100);
}

/** Where the payment page is told it was reached by recording the payment. */
export interface RecordedState {
  recorded: true;
}

interface MemberPickerProps {
  chosen: FinanceMember | null;
  onChoose: (member: FinanceMember | null) => void;
  error?: string;
  /** The search box, which takes the focus back after **Choose somebody else**. */
  searchRef: RefObject<HTMLInputElement | null>;
}

/** The member search, or the member chosen from it with the way to choose again. */
function MemberPicker({ chosen, onChoose, error, searchRef }: MemberPickerProps): JSX.Element {
  const [term, setTerm] = useState('');
  const settled = useDebounced(term);
  const results = useFinanceMemberSearch(settled);

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
    <div className="stack">
      <Field label="Member" error={error} required>
        {(props) => (
          <input
            {...props}
            ref={searchRef}
            type="search"
            placeholder="Search by name or email address"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
          />
        )}
      </Field>
      <p className="visually-hidden" role="status">
        {results.isFetching
          ? 'Searching'
          : results.data !== undefined
            ? `${results.data.length} members found`
            : ''}
      </p>
      {results.isFetching && !results.data ? <p className="muted">Searching…</p> : null}
      {results.data === undefined || results.data.length === 0 ? null : (
        <ul className="member-picker__results">
          {results.data.map((member) => (
            <li key={member.user_id} className="member-picker__result">
              <button
                type="button"
                className="member-picker__button"
                onClick={() => onChoose(member)}
              >
                <span className="member-picker__name">{member.name}</span>
                <span className="member-picker__meta">{member.email}</span>
                <MembershipDot membership={member.membership} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {settled.length > 0 && results.data?.length === 0 ? (
        <p className="muted">No member matches that.</p>
      ) : null}
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
  const record = useRecordPayment();
  const toast = useToast();
  const navigate = useNavigate();
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, record.error);
  const searchRef = useRef<HTMLInputElement>(null);
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
        ? { detail: 'Something went wrong. Please try again.' }
        : {},
  );
  const errors: Record<string, string | undefined> =
    memberError === null ? serverErrors : { ...serverErrors, user_id: memberError };

  useEffect(() => {
    if (!hasPicked) return;
    (member === null ? searchRef : planRef).current?.focus();
  }, [hasPicked, member]);

  function handleChooseMember(chosen: FinanceMember | null) {
    setMember(chosen);
    setMemberError(null);
    setHasPicked(true);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
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
      lede="A check, cash or a bank transfer: the term is activated and the receipt emailed."
    >
      <FinanceTabs current="/admin/payments/list" />

      <Card>
        <form ref={formRef} className="stack" onSubmit={handleSubmit} noValidate>
          <MemberPicker
            chosen={member}
            onChoose={handleChooseMember}
            error={errors.user_id}
            searchRef={searchRef}
          />

          <Field label="Plan" hint="Leave blank for a contribution on its own" error={errors.plan}>
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

          <Field
            label="Contribution"
            hint="Dollars"
            error={errors.contribution_cents ?? errors.amount_cents}
          >
            {(props) => (
              <input
                {...props}
                type="number"
                min="0"
                step="0.01"
                value={contribution}
                onChange={(event) => setContribution(event.target.value)}
              />
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
            hint="The check number, or the transfer's own"
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

          <div className="cluster">
            <Button type="submit" disabled={record.isPending}>
              {record.isPending ? 'Recording…' : 'Record the payment'}
            </Button>
            <RefusedSubmitNote count={refusal.count} />
          </div>
        </form>
      </Card>
    </Page>
  );
}
