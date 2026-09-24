/**
 * The member's own payment history.
 *
 * One row per payment, in the order the API sends them (newest first), with a
 * link to the receipt PDF for every payment whose money arrived.  A refund
 * column appears only when something has come back, so the common case stays
 * four columns wide on a phone.
 */
import type { JSX } from 'react';

import type { PaymentSummary } from '@/portal/api/types';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
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

export interface PaymentsTableProps {
  payments: PaymentSummary[];
}

/** The payments table, or an empty state when the member has paid nothing yet. */
export function PaymentsTable({ payments }: PaymentsTableProps): JSX.Element {
  if (payments.length === 0) {
    return (
      <EmptyState
        title="No payments yet"
        description="Payments you make to CalDART will be listed here, each with its receipt."
      />
    );
  }

  const hasRefunds = payments.some((payment) => payment.refunded_cents > 0);

  return (
    <div className="table-wrap">
      <table className="payments__table">
        <caption className="visually-hidden">Everything you have paid CalDART</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">For</th>
            <th scope="col" className="numeric">
              Amount
            </th>
            {hasRefunds ? (
              <th scope="col" className="numeric">
                Refunded
              </th>
            ) : null}
            <th scope="col">Status</th>
            <th scope="col">Receipt</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.id}>
              <td>
                <DateText value={payment.paid_on ?? payment.completed_at} />
              </td>
              <td>{purchaseLabel(payment)}</td>
              <td className="numeric">
                <Money cents={payment.amount_cents} />
              </td>
              {hasRefunds ? (
                <td className="numeric">
                  {payment.refunded_cents > 0 ? (
                    <Money cents={payment.refunded_cents} />
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              ) : null}
              <td>
                <PaymentChip status={payment.status} />
              </td>
              <td>
                {RECEIPTED.includes(payment.status) ? (
                  <a href={receiptUrl(payment.id)} download>
                    Receipt
                  </a>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
