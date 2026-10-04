/**
 * The member's own payment history.
 *
 * One row per payment, in the order the API sends them (newest first), with a
 * link to the receipt PDF for every payment whose money arrived.  A refund
 * column appears only when something has come back.  On a phone the date, the
 * refund, and the receipt give way, so what was bought, the amount, and the status
 * stay on screen.
 */
import type { JSX } from 'react';

import type { PaymentSummary } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { PaymentChip } from '@/portal/components/StatusChip';
import { receiptUrl } from './api';

/** The statuses whose money arrived, and so have a receipt behind them. */
const RECEIPTED: PaymentSummary['status'][] = ['succeeded', 'partially_refunded', 'refunded'];

/** What one payment bought, in the member's own words. */
export function purchaseLabel(payment: PaymentSummary): string {
  if (payment.kind === 'contribution') return 'Contribution';
  if (payment.kind === 'both') return `${payment.plan ?? 'Membership'} and contribution`;
  return payment.plan ?? 'Membership';
}

/**
 * The history's columns.  What a payment bought identifies a row and stays pinned when
 * the table scrolls; the amount and the status stay in sight on a phone, and the date,
 * the refund, and the receipt drop, in that order, when the table would not fit.  The
 * Refunded column is there only when something has come back.
 */
function paymentColumns(hasRefunds: boolean): Column<PaymentSummary>[] {
  const columns: (Column<PaymentSummary> | null)[] = [
    {
      key: 'date',
      header: 'Date',
      width: '7rem',
      noWrap: true,
      dropOrder: 3,
      render: (payment) => <DateText value={payment.paid_on ?? payment.completed_at} />,
    },
    {
      key: 'for',
      header: 'For',
      // Narrow enough that what it bought, the amount, and the status fit a phone.
      minWidth: '6rem',
      isIdentity: true,
      render: (payment) => purchaseLabel(payment),
    },
    {
      key: 'amount',
      header: 'Amount',
      width: '6rem',
      numeric: true,
      keepInSight: true,
      render: (payment) => <Money cents={payment.amount_cents} />,
    },
    hasRefunds
      ? {
          key: 'refunded',
          header: 'Refunded',
          width: '6.5rem',
          numeric: true,
          dropOrder: 1,
          render: (payment) =>
            payment.refunded_cents > 0 ? (
              <Money cents={payment.refunded_cents} />
            ) : (
              <span className="muted">—</span>
            ),
        }
      : null,
    {
      key: 'status',
      header: 'Status',
      width: '9rem',
      narrowWidth: '7rem',
      keepInSight: true,
      render: (payment) => <PaymentChip status={payment.status} />,
    },
    {
      key: 'receipt',
      header: 'Receipt',
      width: '6rem',
      dropOrder: 2,
      render: (payment) =>
        RECEIPTED.includes(payment.status) ? (
          <a href={receiptUrl(payment.id)} download>
            Receipt
          </a>
        ) : (
          <span className="muted">—</span>
        ),
    },
  ];
  return columns.filter((column) => column !== null);
}

export interface PaymentsTableProps {
  payments: PaymentSummary[];
}

/** The payments table, or an empty state when the member has paid nothing yet. */
export function PaymentsTable({ payments }: PaymentsTableProps): JSX.Element {
  const hasRefunds = payments.some((payment) => payment.refunded_cents > 0);
  return (
    <DataTable
      singleLine
      columns={paymentColumns(hasRefunds)}
      rows={payments}
      rowKey={(payment) => payment.id}
      caption="Everything you have paid CalDART"
      emptyTitle="No payments yet"
      emptyDescription="Payments you make to CalDART will be listed here, each with its receipt."
    />
  );
}
