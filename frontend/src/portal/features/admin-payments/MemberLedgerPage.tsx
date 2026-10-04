/**
 * `/admin/payments/members/:userId` — one member's whole money history.
 *
 * Everything a question about one member's money needs in one screen: what
 * they have paid over the years, every payment with what came back out of it,
 * their standing renewal authority, and the contribution statements they can
 * be sent.  The Payments tab of the member record draws the same cards from
 * the same endpoint, which is why the body is a component of its own.
 */
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { MemberLedger, PaymentDetail, RenewalMandate } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Loading } from '@/portal/components/Loading';
import { MemberRecordLink } from '@/portal/components/MemberRecordLink';
import { Money, formatCents } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { MembershipDot, StatusDot } from '@/portal/components/StatusDot';
import { statementUrl, useMemberLedger } from './api';
import { FinanceTabs } from './FinanceTabs';
import {
  KIND_LABELS,
  MANDATE_KIND_LABELS,
  MANDATE_STATUS_LABELS,
  PROVIDER_LABELS,
  STATUS_LABELS,
  statusTone,
} from './labels';
import './admin-payments.css';

/**
 * The payment history's columns.  The receipt number identifies a row and never
 * wraps; Total and Status stay in sight on a phone, and the rest drop when the table
 * would not fit.
 */
const LEDGER_COLUMNS: Column<PaymentDetail>[] = [
  {
    key: 'paid_on',
    header: 'Paid',
    width: '7rem',
    noWrap: true,
    dropOrder: 3,
    render: (row) => <DateText value={row.paid_on} />,
  },
  {
    key: 'receipt_number',
    header: 'Receipt',
    width: '10rem',
    isIdentity: true,
    render: (row) => <Link to={`/admin/payments/${row.id}`}>{row.receipt_number}</Link>,
  },
  {
    key: 'kind',
    header: 'For',
    minWidth: '8rem',
    dropOrder: 2,
    render: (row) => KIND_LABELS[row.kind],
  },
  {
    key: 'amount_cents',
    header: 'Total',
    width: '6.5rem',
    keepInSight: true,
    numeric: true,
    render: (row) => <Money cents={row.amount_cents} />,
  },
  {
    key: 'refunded_cents',
    header: 'Refunded',
    width: '6.5rem',
    dropOrder: 1,
    numeric: true,
    render: (row) => <Money cents={row.refunded_cents} />,
  },
  {
    key: 'provider',
    header: 'Method',
    width: '6.5rem',
    dropOrder: 1,
    render: (row) => PROVIDER_LABELS[row.provider],
  },
  {
    key: 'status',
    header: 'Status',
    width: '9rem',
    narrowWidth: '7rem',
    keepInSight: true,
    render: (row) => <StatusDot tone={statusTone(row.status)} label={STATUS_LABELS[row.status]} />,
  },
];

/** The mandate card: how this member's membership renews itself, if it does. */
export function MandateCard({ mandate }: { mandate: RenewalMandate | null }): JSX.Element {
  if (mandate === null) {
    return (
      <Card title="Automatic renewal">
        <p className="muted">This member renews by hand.</p>
      </Card>
    );
  }
  return (
    <Card title={MANDATE_KIND_LABELS[mandate.kind]}>
      <dl className="payment-facts">
        <div>
          <dt>State</dt>
          <dd>{MANDATE_STATUS_LABELS[mandate.status]}</dd>
        </div>
        <div>
          <dt>Method</dt>
          <dd>{mandate.method_label}</dd>
        </div>
        <div>
          <dt>Charges</dt>
          <dd>
            {mandate.plan_name ?? 'Contribution'} · {formatCents(mandate.amount_cents)}
          </dd>
        </div>
        <div>
          <dt>Next charge</dt>
          <dd>
            <DateText value={mandate.next_charge_on} />
          </dd>
        </div>
        {mandate.last_error === '' ? null : (
          <div>
            <dt>Last refusal</dt>
            <dd>{mandate.last_error}</dd>
          </div>
        )}
      </dl>
    </Card>
  );
}

/** The ledger's three cards, for the finance screen and the member record alike. */
export function LedgerBody({ ledger }: { ledger: MemberLedger }): JSX.Element {
  return (
    <>
      <Card title="Totals" eyebrow="Whole history">
        <dl className="payment-facts">
          <div>
            <dt>Paid</dt>
            <dd>
              <Money cents={ledger.totals.paid_cents} />
            </dd>
          </div>
          <div>
            <dt>Contributed</dt>
            <dd>
              <Money cents={ledger.totals.contribution_cents} />
            </dd>
          </div>
          <div>
            <dt>Fees</dt>
            <dd>
              <Money cents={ledger.totals.fee_cents} />
            </dd>
          </div>
          <div>
            <dt>Refunded</dt>
            <dd>
              <Money cents={ledger.totals.refunded_cents} />
            </dd>
          </div>
        </dl>
      </Card>

      <MandateCard mandate={ledger.mandate} />

      <Card title="Payments">
        <DataTable
          singleLine
          columns={LEDGER_COLUMNS}
          rows={ledger.payments}
          rowKey={(row) => row.id}
          emptyTitle="No payments recorded"
          emptyDescription="Terms granted by an administrator have no payment attached."
        />
      </Card>

      <Card title="Contribution statements">
        {ledger.statement_years.length === 0 ? (
          <p className="muted">This member has not given anything beyond their dues.</p>
        ) : (
          <div className="cluster">
            {ledger.statement_years.map((year) => (
              <a
                key={year}
                className="button button--quiet button--small"
                href={statementUrl(ledger.user.id, year)}
              >
                {year}
              </a>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

/** `/admin/payments/members/:userId`: one member's money, whole. */
export function MemberLedgerPage(): JSX.Element {
  const { userId } = useParams();
  const id = Number(userId);
  const query = useMemberLedger(Number.isFinite(id) ? id : null);

  if (query.isPending) return <Loading />;
  if (query.error || !query.data) {
    return (
      <Page title="Member ledger">
        <FinanceTabs current="/admin/payments/list" />
        <EmptyState
          title="That ledger could not be loaded"
          description="The member may have been removed, or you may not have permission to see them."
        />
      </Page>
    );
  }

  const ledger = query.data;

  return (
    <Page
      title={ledger.user.name}
      lede={ledger.user.email}
      actions={
        <>
          <MembershipDot membership={ledger.user.membership} />
          <MemberRecordLink userId={ledger.user.id} isTombstone={ledger.user.is_tombstone} />
        </>
      }
    >
      <FinanceTabs current="/admin/payments/list" />
      <LedgerBody ledger={ledger} />
    </Page>
  );
}
