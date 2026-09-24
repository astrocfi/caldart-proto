/**
 * `/admin/payments` — the finance area's overview.
 *
 * What the money did: four figures for each of three periods, then the same
 * money per month or per year with a column for each provider.  The list
 * itself, the writes and the reports are the other tabs; this screen answers
 * "how are we doing" without anybody having to filter anything.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';

import { ButtonLink } from '@/portal/components/Button';
import { Page } from '@/portal/components/Page';
import { EMPTY_FILTERS, dashboardTotals, useAdminPaymentSummary, useMonthlyTotals } from './api';
import type { PaymentFilterState, SummaryGroup } from './api';
import { FilterBar } from './FilterBar';
import { FinanceTabs } from './FinanceTabs';
import { PeriodTable } from './PeriodTable';
import { SummaryTiles } from './SummaryTiles';
import './admin-payments.css';

/** `/admin/payments`: the tiles and the period table. */
export function AdminPaymentsPage(): JSX.Element {
  const [filters, setFilters] = useState<PaymentFilterState>(EMPTY_FILTERS);
  const [group, setGroup] = useState<SummaryGroup>('month');

  const monthly = useMonthlyTotals();
  const summary = useAdminPaymentSummary(group, filters);

  const totals = useMemo(() => dashboardTotals(monthly.data ?? []), [monthly.data]);

  function handleFilterChange(next: PaymentFilterState) {
    setFilters(next);
  }

  return (
    <Page
      title="Payments"
      eyebrow="Finance"
      lede="What CalDART took, what the providers kept, and what reached the bank."
      actions={<ButtonLink to="/admin/payments/list">All payments</ButtonLink>}
    >
      <FinanceTabs />

      <SummaryTiles totals={totals} isLoading={monthly.isPending} />

      <PeriodTable
        rows={summary.data ?? []}
        group={group}
        onGroupChange={(next) => setGroup(next)}
        isLoading={summary.isPending}
        filters={<FilterBar value={filters} onChange={handleFilterChange} compact />}
      />
    </Page>
  );
}
