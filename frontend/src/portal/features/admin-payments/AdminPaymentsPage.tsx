/**
 * `/admin/payments` — the account administrator's money screen.
 *
 * Three headline tiles, a month/year table broken down by provider, then the
 * filtered payment list with a CSV export that carries the same filters.
 *
 * Sorting and paging both go to the server, so ordering a column reorders the
 * whole report rather than just the page on screen.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { Payment } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import {
  EMPTY_FILTERS,
  dashboardTotals,
  exportCsvUrl,
  useAdminPaymentSummary,
  useAdminPayments,
  useMonthlyTotals,
} from './api';
import type { PaymentFilterState, SummaryGroup } from './api';
import { FilterBar } from './FilterBar';
import { PROVIDER_LABELS, STATUS_LABELS, WALLET_LABELS, statusTone } from './labels';
import { PeriodTable } from './PeriodTable';
import { SummaryTiles } from './SummaryTiles';
import './admin-payments.css';

const PAGE_SIZE = 25;

/** Column keys are the `ordering` values the API accepts. */
const COLUMNS: Column<Payment>[] = [
  {
    key: 'paid_at',
    header: 'Paid',
    render: (row) => <DateText value={row.completed_at ?? row.created_at} />,
  },
  {
    key: 'user__last_name',
    header: 'Member',
    render: (row) => <Link to={`/admin/members/${row.user_id}`}>{row.user_name}</Link>,
  },
  { key: 'plan__name', header: 'Plan', render: (row) => row.plan ?? 'Contribution only' },
  {
    key: 'contribution_cents',
    header: 'Contribution',
    numeric: true,
    render: (row) => <Money cents={row.contribution_cents} />,
  },
  {
    key: 'amount_cents',
    header: 'Total',
    numeric: true,
    render: (row) => <Money cents={row.amount_cents} />,
  },
  {
    key: 'provider',
    header: 'Method',
    render: (row) => (
      <span>
        {PROVIDER_LABELS[row.provider]}
        {row.wallet && row.wallet !== 'unknown' ? (
          <span className="muted"> · {WALLET_LABELS[row.wallet]}</span>
        ) : null}
      </span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (row) => <StatusChip tone={statusTone(row.status)} label={STATUS_LABELS[row.status]} />,
  },
];

/** `/admin/payments` page: the filterable payment list plus its summary dashboard. */
export function AdminPaymentsPage(): JSX.Element {
  const [filters, setFilters] = useState<PaymentFilterState>(EMPTY_FILTERS);
  const [group, setGroup] = useState<SummaryGroup>('month');
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState('-paid_at');

  const monthly = useMonthlyTotals();
  const summary = useAdminPaymentSummary(group, filters);
  const list = useAdminPayments(filters, { page, pageSize: PAGE_SIZE, ordering });

  const totals = useMemo(() => dashboardTotals(monthly.data ?? []), [monthly.data]);
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE));

  function handleFilterChange(next: PaymentFilterState) {
    setFilters(next);
    setPage(1);
  }

  return (
    <Page
      title="Payments"
      eyebrow="Reports"
      lede="Every membership payment and contribution, with monthly and yearly totals."
    >
      <SummaryTiles totals={totals} isLoading={monthly.isPending} />

      <PeriodTable
        rows={summary.data ?? []}
        group={group}
        onGroupChange={(next) => setGroup(next)}
        isLoading={summary.isPending}
      />

      <section className="stack">
        <h2 className="period-table__title">All payments</h2>
        <DataTable
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => row.id}
          caption={`${count} payment${count === 1 ? '' : 's'}`}
          filters={<FilterBar value={filters} onChange={handleFilterChange} />}
          exportCsvUrl={exportCsvUrl(filters)}
          isLoading={list.isPending}
          emptyTitle="No payments match these filters"
          emptyDescription="Try a wider date range, or clear the filters."
          initialSort={{ key: 'paid_at', direction: 'desc' }}
          onSortChange={(key, direction) => {
            setOrdering(`${direction === 'desc' ? '-' : ''}${key}`);
            setPage(1);
          }}
        />

        {lastPage > 1 ? (
          <nav className="pager" aria-label="Payment pages">
            <Button
              variant="quiet"
              small
              disabled={page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              Previous
            </Button>
            <span className="muted pager__status" aria-live="polite">
              Page {page} of {lastPage}
            </span>
            <Button
              variant="quiet"
              small
              disabled={page >= lastPage}
              onClick={() => setPage((current) => Math.min(lastPage, current + 1))}
            >
              Next
            </Button>
          </nav>
        ) : null}
      </section>
    </Page>
  );
}
