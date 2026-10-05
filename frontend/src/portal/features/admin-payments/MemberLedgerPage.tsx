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
import { isWithoutTerm } from '@/portal/choices';
import { statementUrl, useMemberLedger } from './api';
import { FinanceTabs } from './FinanceTabs';
import {
  MANDATE_KIND_LABELS,
  MANDATE_STATUS_LABELS,
  PROVIDER_LABELS,
  STATUS_LABELS,
  paymentForLabel,
  statusTone,
} from './labels';
import './admin-payments.css';

/**
 * The payment history's columns.  The date tells one payment from the next and stays
 * pinned when the table scrolls; the receipt number keeps its whole width, since every
 * receipt starts alike and a cut one reads the same as its neighbors.  Total and Status
 * stay in sight on a phone, and the rest drop when the table would not fit.
 */
export const LEDGER_COLUMNS: Column<PaymentDetail>[] = [
  {
    key: 'paid_on',
    header: 'Paid',
    width: '7rem',
    isIdentity: true,
    render: (row) => <DateText value={row.paid_on} />,
  },
  {
    key: 'receipt_number',
    header: 'Receipt',
    width: '10rem',
    noWrap: true,
    render: (row) => <Link to={`/admin/payments/${row.id}`}>{row.receipt_number}</Link>,
  },
  {
    key: 'kind',
    header: 'For',
    minWidth: '8rem',
    dropOrder: 2,
    render: (row) => paymentForLabel(row),
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
            {mandate.plan_name ?? 'Donation'} · {formatCents(mandate.amount_cents)}
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
            <dt>Last failed charge</dt>
            <dd>{mandate.last_error}</dd>
          </div>
        )}
      </dl>
    </Card>
  );
}

/**
 * The ledger's cards, for the finance screen and the member record alike.  Somebody with
 * no membership to renew (a friend, or a member who has not paid yet) and no standing
 * authority gets no renewal card, and their statements card says nothing of dues.
 */
export function LedgerBody({ ledger }: { ledger: MemberLedger }): JSX.Element {
  const hasNoMembership = isWithoutTerm(ledger.user.membership.status);
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

      {ledger.mandate === null && hasNoMembership ? null : (
        <MandateCard mandate={ledger.mandate} />
      )}

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
          <p className="muted">
            {hasNoMembership
              ? 'This person has not given anything yet.'
              : 'This member has not given anything beyond their dues.'}
          </p>
        ) : (
          <div className="cluster">
            {ledger.statement_years.map((year) => (
              <a
                key={year}
                className="button button--quiet button--small"
                href={statementUrl(ledger.user.id, year)}
                aria-label={`Download the ${year} contribution statement (PDF)`}
              >
                {`Download ${year} statement`}
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
          title="That ledger didn't load"
          description="The member may have been removed, or you may not have permission to see them."
        />
      </Page>
    );
  }

  const ledger = query.data;

  return (
    <Page
      title={ledger.user.name}
      tabTitle={`${ledger.user.name} · Money history`}
      lede={ledger.user.email}
      actions={
        <>
          <span className="cluster">
            Membership: <MembershipDot membership={ledger.user.membership} />
          </span>
          <MemberRecordLink userId={ledger.user.id} isTombstone={ledger.user.is_tombstone} />
        </>
      }
    >
      <FinanceTabs current="/admin/payments/list" />
      <LedgerBody ledger={ledger} />
    </Page>
  );
}
