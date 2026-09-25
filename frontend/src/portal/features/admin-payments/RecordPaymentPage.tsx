/**
 * `/admin/payments/record` — money that arrived by check, cash or transfer.
 *
 * The member is found by typing, as on the member list, because a treasurer
 * has a check in their hand and a name on it rather than an id.  Everything
 * else is the same decision a card checkout makes: which plan, how much of it
 * is a gift, and when the money arrived.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { usePlans } from '@/portal/api/queries';
import type { FinanceMember, ManualMethod } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { todayIso } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { MembershipChip } from '@/portal/components/StatusChip';
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

interface MemberPickerProps {
  chosen: FinanceMember | null;
  onChoose: (member: FinanceMember | null) => void;
  error?: string;
}

function MemberPicker({ chosen, onChoose, error }: MemberPickerProps): JSX.Element {
  const [term, setTerm] = useState('');
  const settled = useDebounced(term);
  const results = useFinanceMemberSearch(settled);

  if (chosen !== null) {
    return (
      <div className="record-payment__chosen">
        <p>
          <strong>{chosen.name}</strong> <span className="muted">{chosen.email}</span>{' '}
          <MembershipChip membership={chosen.membership} />
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
                <MembershipChip membership={member.membership} />
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
  const [errors, setErrors] = useState<Record<string, string>>({});

  const plans = usePlans();
  const record = useRecordPayment();
  const toast = useToast();
  const navigate = useNavigate();

  function handleChooseMember(chosen: FinanceMember | null) {
    setMember(chosen);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setErrors({});
    if (member === null) {
      setErrors({ user_id: 'Choose the member this payment is for.' });
      return;
    }
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
          void navigate(`/admin/payments/${payment.id}`);
        },
        onError: (error) => {
          if (error instanceof ApiError) setErrors(reportedErrors(error));
          else setErrors({ detail: 'Something went wrong. Please try again.' });
        },
      },
    );
  }

  return (
    <Page
      title="Record a payment"
      eyebrow="Finance"
      lede="A check, cash or a bank transfer: the term is activated and the receipt emailed."
    >
      <FinanceTabs current="/admin/payments/list" />

      <Card>
        <form className="stack" onSubmit={handleSubmit}>
          <MemberPicker chosen={member} onChoose={handleChooseMember} error={errors.user_id} />

          <Field label="Plan" hint="Leave blank for a contribution on its own" error={errors.plan}>
            {(props) => (
              <select {...props} value={plan} onChange={(event) => setPlan(event.target.value)}>
                <option value="">No membership</option>
                {(plans.data ?? []).map((option) => (
                  <option key={option.slug} value={option.slug}>
                    {option.name}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field label="Contribution" hint="Dollars" error={errors.contribution_cents}>
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

          <Button type="submit" disabled={record.isPending}>
            {record.isPending ? 'Recording…' : 'Record the payment'}
          </Button>
        </form>
      </Card>
    </Page>
  );
}
