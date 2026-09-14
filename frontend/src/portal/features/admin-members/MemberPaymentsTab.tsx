/**
 * The Payments tab: what this member has paid, newest first.
 *
 * The full payment ledger and its month/year summary live on
 * `/admin/payments`; this table is the per-member slice an administrator needs
 * while looking at one record.
 */
import { Card, DataTable, DateText, Money, PaymentChip } from '../../components';
import type { Column } from '../../components';
import type { MemberDetail, MemberPayment } from './types';

const COLUMNS: Column<MemberPayment>[] = [
  {
    key: 'created_at',
    header: 'Date',
    render: (payment) => <DateText value={payment.completed_at ?? payment.created_at} withTime />,
  },
  { key: 'plan', header: 'For', render: (payment) => payment.plan ?? 'Contribution' },
  {
    key: 'plan_amount_cents',
    header: 'Membership',
    numeric: true,
    render: (payment) => <Money cents={payment.plan_amount_cents} />,
  },
  {
    key: 'contribution_cents',
    header: 'Contribution',
    numeric: true,
    render: (payment) => <Money cents={payment.contribution_cents} />,
  },
  {
    key: 'amount_cents',
    header: 'Total',
    numeric: true,
    render: (payment) => <Money cents={payment.amount_cents} />,
  },
  { key: 'provider', header: 'Provider', render: (payment) => payment.provider },
  {
    key: 'status',
    header: 'Status',
    render: (payment) => <PaymentChip status={payment.status} />,
  },
];

export function MemberPaymentsTab({ member }: { member: MemberDetail }) {
  return (
    <Card title="Payments" eyebrow="History">
      <DataTable
        columns={COLUMNS}
        rows={member.payments}
        rowKey={(payment) => payment.id}
        emptyTitle="No payments recorded"
        emptyDescription="Terms granted by an administrator have no payment attached."
      />
    </Card>
  );
}
