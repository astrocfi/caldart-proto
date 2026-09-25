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
import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

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
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
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
  PROVIDER_LABELS,
  REFUND_REASON_LABELS,
  REFUND_STATUS_LABELS,
  STATUS_LABELS,
  WALLET_LABELS,
  statusTone,
} from './labels';
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
          <Link to={`/admin/payments/members/${payment.user_id}`}>{payment.user_name}</Link>{' '}
          <span className="muted">{payment.user_email}</span>
        </dd>
      </div>
      <div>
        <dt>Receipt</dt>
        <dd className="mono">{payment.receipt_number}</dd>
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
        <dd>
          {PROVIDER_LABELS[payment.provider]} · {WALLET_LABELS[payment.wallet]}
        </dd>
      </div>
      <div>
        <dt>Reference</dt>
        <dd className="mono">{payment.provider_ref || '—'}</dd>
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
            'None'
          ) : (
            <>
              <DateText value={payment.membership.starts_on} /> to{' '}
              <DateText value={payment.membership.ends_on} /> · {payment.membership.status}
            </>
          )}
        </dd>
      </div>
      <div>
        <dt>{PAYMENT_AUTOMATIC_LABELS[payment.kind]}</dt>
        <dd>
          {payment.renewal_attempt === null ? (
            'Paid by a person'
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
  const [error, setError] = useState<string | null>(null);
  const patch = usePatchPayment(payment.id);
  const toast = useToast();

  function handleSave() {
    setError(null);
    patch.mutate(
      { reconciled_on: reconciledOn === '' ? null : reconciledOn, note },
      {
        onSuccess: () => toast.show('Payment updated.', 'success'),
        onError: (failure) =>
          setError(
            failure instanceof ApiError ? failure.message : 'Something went wrong. Try again.',
          ),
      },
    );
  }

  return (
    <Card title="Reconciliation" eyebrow="Treasurer">
      <Field
        label="Matched on"
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
      <Field label="Note" hint="A check number, or why this entry exists">
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
        <p className="muted">Matched by {payment.reconciled_by}.</p>
      )}
      <Button onClick={handleSave} disabled={patch.isPending}>
        {patch.isPending ? 'Saving…' : 'Save'}
      </Button>
    </Card>
  );
}

/** `/admin/payments/:id`: one payment, its refunds, and what can be done to it. */
export function PaymentDetailPage(): JSX.Element {
  const { id } = useParams();
  const paymentId = Number(id);
  const query = usePaymentDetail(Number.isFinite(paymentId) ? paymentId : null);
  const [isRefunding, setIsRefunding] = useState(false);

  const resend = useResendReceipt(paymentId);
  const fees = useFetchFees(paymentId);
  const toast = useToast();

  if (query.isPending) return <Loading />;
  if (query.error || !query.data) {
    return (
      <Page title="Payment" eyebrow="Finance">
        <FinanceTabs current="/admin/payments/list" />
        <EmptyState
          title="That payment could not be loaded"
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
      eyebrow="Finance"
      lede={`${payment.user_name} · ${STATUS_LABELS[payment.status]}`}
      actions={
        <StatusChip tone={statusTone(payment.status)} label={STATUS_LABELS[payment.status]} />
      }
    >
      <FinanceTabs current="/admin/payments/list" />

      <Card title="This payment" eyebrow="Record">
        <Facts payment={payment} />
        <div className="cluster">
          <Button onClick={() => setIsRefunding(true)} disabled={isRefunding}>
            Refund
          </Button>
          <Button variant="secondary" onClick={handleResend} disabled={resend.isPending}>
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
        </div>
      </Card>

      {isRefunding ? (
        <Card>
          <RefundForm
            payment={payment}
            onDone={() => setIsRefunding(false)}
            onCancel={() => setIsRefunding(false)}
          />
        </Card>
      ) : null}

      <Card title="Refunds" eyebrow="History">
        <DataTable
          columns={REFUND_COLUMNS}
          rows={payment.refunds}
          rowKey={(row) => row.id}
          emptyTitle="Nothing has been refunded"
          emptyDescription="A refund issued here or in the provider's dashboard appears in this table."
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
