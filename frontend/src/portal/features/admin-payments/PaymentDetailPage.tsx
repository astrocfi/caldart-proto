/**
 * `/admin/payments/:id` — one payment, everything about it, and what can be
 * done to it.
 *
 * The facts first, then the refunds against it, then the treasurer's own two
 * fields: the day it was matched to a statement and the note that says which
 * check it was.  The actions — refund, resend the receipt, download it, ask the
 * provider for the fee — all answer with the payment as it now stands, so the
 * screen redraws from the answer rather than guessing.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { PaymentDetail, Refund } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { Loading } from '@/portal/components/Loading';
import { MemberRecordLink } from '@/portal/components/MemberRecordLink';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { useFreshErrors, useRefusedSubmit } from '@/portal/components/RefusedSubmit';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { useFocusAfterSave, usePanelFocus } from '@/portal/components/focus';
import {
  receiptUrl,
  useFetchFees,
  usePatchPayment,
  usePaymentDetail,
  useResendReceipt,
} from './api';
import { FinanceTabs } from './FinanceTabs';
import {
  KIND_LABELS,
  PAYMENT_AUTOMATIC_LABELS,
  REFUND_REASON_LABELS,
  REFUND_STATUS_LABELS,
  STATUS_LABELS,
  TERM_STATUS_LABELS,
  methodLabel,
  statusTone,
} from './labels';
import type { RecordedState } from './RecordPaymentPage';
import { RefundForm } from './RefundForm';
import './admin-payments.css';

const REFUND_COLUMNS: Column<Refund>[] = [
  { key: 'created_at', header: 'Issued', render: (row) => <DateText value={row.created_at} /> },
  {
    key: 'amount_cents',
    header: 'Amount',
    numeric: true,
    render: (row) => <Money cents={row.amount_cents} />,
  },
  { key: 'reason', header: 'Reason', render: (row) => REFUND_REASON_LABELS[row.reason] },
  { key: 'note', header: 'Note', render: (row) => row.note },
  { key: 'status', header: 'Status', render: (row) => REFUND_STATUS_LABELS[row.status] },
  {
    key: 'requested_by_id',
    header: 'Source',
    render: (row) =>
      row.requested_by_id === null ? "The provider's dashboard" : 'The CalDART portal',
  },
];

/** Whether the provider has told CalDART what this payment cost. */
export function feesAreKnown(payment: PaymentDetail): boolean {
  return payment.amount_cents === 0 || payment.net_cents > 0;
}

interface FactsProps {
  payment: PaymentDetail;
}

function Facts({ payment }: FactsProps): JSX.Element {
  return (
    <dl className="payment-facts">
      <div>
        <dt>Member</dt>
        <dd>
          {payment.user_name} <span className="muted">{payment.user_email}</span>
          <span className="payment-facts__links">
            <Link to={`/admin/payments/members/${payment.user_id}`}>Money history</Link>
            <MemberRecordLink userId={payment.user_id} isTombstone={payment.user_is_tombstone} />
          </span>
        </dd>
      </div>
      <div>
        <dt>Receipt</dt>
        <dd className="num">{payment.receipt_number}</dd>
      </div>
      <div>
        <dt>For</dt>
        <dd>
          {KIND_LABELS[payment.kind]}
          {payment.plan === null ? '' : ` · ${payment.plan}`}
        </dd>
      </div>
      <div>
        <dt>Paid</dt>
        <dd>
          <DateText value={payment.paid_on} />
        </dd>
      </div>
      <div>
        <dt>Dues</dt>
        <dd>
          <Money cents={payment.plan_amount_cents} />
        </dd>
      </div>
      <div>
        <dt>Contribution</dt>
        <dd>
          <Money cents={payment.contribution_cents} />
        </dd>
      </div>
      <div>
        <dt>Total</dt>
        <dd>
          <Money cents={payment.amount_cents} />
        </dd>
      </div>
      <div>
        <dt>Fee</dt>
        <dd>{feesAreKnown(payment) ? <Money cents={payment.fee_cents} /> : 'Not reported yet'}</dd>
      </div>
      <div>
        <dt>Net</dt>
        <dd>{feesAreKnown(payment) ? <Money cents={payment.net_cents} /> : '—'}</dd>
      </div>
      <div>
        <dt>Refunded</dt>
        <dd>
          <Money cents={payment.refunded_cents} />
        </dd>
      </div>
      <div>
        <dt>Method</dt>
        <dd>{methodLabel(payment.provider, payment.wallet)}</dd>
      </div>
      <div>
        <dt>Reference</dt>
        <dd className="num">{payment.provider_ref || '—'}</dd>
      </div>
      <div>
        <dt>Receipt emailed</dt>
        <dd>
          <DateText value={payment.receipt_sent_at} withTime />
        </dd>
      </div>
      <div>
        <dt>Term</dt>
        <dd>
          {payment.membership === null ? (
            '—'
          ) : (
            <>
              <DateText value={payment.membership.starts_on} /> to{' '}
              <DateText value={payment.membership.ends_on} /> ·{' '}
              {TERM_STATUS_LABELS[payment.membership.status]}
            </>
          )}
        </dd>
      </div>
      <div>
        <dt>{PAYMENT_AUTOMATIC_LABELS[payment.kind]}</dt>
        <dd>
          {payment.renewal_attempt === null ? (
            'No, paid by the member'
          ) : (
            <>
              Charged on <DateText value={payment.renewal_attempt.scheduled_on} />
            </>
          )}
        </dd>
      </div>
      {payment.recorded_by === null ? null : (
        <div>
          <dt>Recorded by</dt>
          <dd>{payment.recorded_by}</dd>
        </div>
      )}
    </dl>
  );
}

interface ReconcileCardProps {
  payment: PaymentDetail;
}

function ReconcileCard({ payment }: ReconcileCardProps): JSX.Element {
  const [reconciledOn, setReconciledOn] = useState(payment.reconciled_on ?? '');
  const [note, setNote] = useState(payment.note);
  const patch = usePatchPayment(payment.id);
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  useRefusedSubmit(formRef, patch.error);
  useFocusAfterSave(formRef, patch.isPending);
  // What the server said about the date goes once the date is edited.
  const { error } = useFreshErrors(
    patch.error,
    { error: reconciledOn },
    {
      error: patch.error
        ? patch.error instanceof ApiError
          ? patch.error.message
          : "The reconciliation wasn't saved. Try again in a moment."
        : null,
    },
  );

  function handleSave(event: FormEvent) {
    event.preventDefault();
    patch.mutate(
      { reconciled_on: reconciledOn === '' ? null : reconciledOn, note },
      { onSuccess: () => toast.show('Payment updated.', 'success') },
    );
  }

  return (
    <Card title="Reconciliation">
      <form ref={formRef} className="stack finance-form" onSubmit={handleSave} noValidate>
        <Field
          label="Reconciled on"
          hint="The day this payment was found on a statement"
          error={error ?? undefined}
        >
          {(props) => (
            <input
              {...props}
              type="date"
              value={reconciledOn}
              onChange={(event) => setReconciledOn(event.target.value)}
            />
          )}
        </Field>
        <Field label="Note" hint="Anything worth keeping with this payment">
          {(props) => (
            <input
              {...props}
              type="text"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          )}
        </Field>
        {payment.reconciled_by === null ? null : (
          <p className="muted">Reconciled by {payment.reconciled_by}.</p>
        )}
        <Button type="submit" disabled={patch.isPending}>
          {patch.isPending ? 'Saving…' : 'Save changes'}
        </Button>
      </form>
    </Card>
  );
}

/** `/admin/payments/:id`: one payment, its refunds, and what can be done to it. */
export function PaymentDetailPage(): JSX.Element {
  const { id } = useParams();
  const paymentId = Number(id);
  const query = usePaymentDetail(Number.isFinite(paymentId) ? paymentId : null);
  const [isRefunding, setIsRefunding] = useState(false);
  const handleStopRefunding = useCallback(() => setIsRefunding(false), []);
  const refundRef = useRef<HTMLButtonElement>(null);
  const refundFormRef = usePanelFocus(
    isRefunding ? 'refund' : null,
    handleStopRefunding,
    refundRef,
  );
  const resendRef = useRef<HTMLButtonElement>(null);

  const resend = useResendReceipt(paymentId);
  const fees = useFetchFees(paymentId);
  const toast = useToast();
  useFocusAfterSave(resendRef, resend.isPending);

  // Arriving from Record a payment, the focus starts on the payment's own heading
  // rather than on the page body, so the treasurer hears which payment it is.
  const location = useLocation();
  const hasArrived = query.data !== undefined;
  useEffect(() => {
    const state = location.state as Partial<RecordedState> | null;
    if (!hasArrived || state?.recorded !== true) return;
    const heading = document.querySelector<HTMLElement>('h1');
    if (heading === null) return;
    heading.tabIndex = -1;
    heading.focus();
  }, [hasArrived, location.state]);

  if (query.isPending) return <Loading />;
  if (query.error || !query.data) {
    return (
      <Page title="Payment">
        <FinanceTabs current="/admin/payments/list" />
        <EmptyState
          title="That payment didn't load"
          description="It may have been removed, or you may not have permission to see it."
        />
      </Page>
    );
  }

  const payment = query.data;

  function handleResend() {
    resend.mutate(undefined, {
      onSuccess: () => toast.show('Receipt emailed again.', 'success'),
      onError: (error) => toast.show(error.message, 'error'),
    });
  }

  function handleFetchFees() {
    fees.mutate(undefined, {
      onSuccess: () => toast.show('Fee read from the provider.', 'success'),
      onError: (error) => toast.show(error.message, 'error'),
    });
  }

  return (
    <Page
      title={`Payment ${payment.receipt_number}`}
      lede={payment.user_name}
      actions={
        <StatusDot tone={statusTone(payment.status)} label={STATUS_LABELS[payment.status]} />
      }
    >
      <FinanceTabs current="/admin/payments/list" />

      <Card title="This payment">
        <Facts payment={payment} />
        {/* One style for every action, and Refund, the one that gives money back, last. */}
        <div className="cluster">
          <Button
            ref={resendRef}
            variant="quiet"
            onClick={handleResend}
            disabled={resend.isPending}
          >
            {resend.isPending ? 'Sending…' : 'Resend receipt'}
          </Button>
          <a className="button button--quiet" href={receiptUrl(payment.id)}>
            Download receipt
          </a>
          {feesAreKnown(payment) ? null : (
            <Button variant="quiet" onClick={handleFetchFees} disabled={fees.isPending}>
              {fees.isPending ? 'Asking…' : 'Fetch fee from provider'}
            </Button>
          )}
          <Button
            ref={refundRef}
            variant="quiet"
            aria-expanded={isRefunding}
            onClick={() => setIsRefunding((current) => !current)}
          >
            Refund
          </Button>
        </div>
      </Card>

      {isRefunding ? (
        <div ref={refundFormRef}>
          <Card>
            <RefundForm
              payment={payment}
              onDone={handleStopRefunding}
              onCancel={handleStopRefunding}
            />
          </Card>
        </div>
      ) : null}

      <Card title="Refunds">
        <DataTable
          columns={REFUND_COLUMNS}
          rows={payment.refunds}
          rowKey={(row) => row.id}
          emptyTitle="Nothing has been refunded"
          emptyDescription="Refunds made here or in the provider's dashboard are listed here."
        />
      </Card>

      <ReconcileCard payment={payment} />

      <p>
        <Link to={`/admin/payments/members/${payment.user_id}`}>
          Everything {payment.user_name} has paid
        </Link>
      </p>
    </Page>
  );
}
