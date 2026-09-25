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
import { FilterBar } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import { dashboardTotals, useAdminPaymentSummary, useMonthlyTotals } from './api';
import type { SummaryGroup } from './api';
import { FinanceTabs } from './FinanceTabs';
import { PeriodTable } from './PeriodTable';
import { SummaryTiles } from './SummaryTiles';
import './admin-payments.css';

/**
 * The payments report's filters the period table offers: the range, where the
 * money came from, its state, and a search.  The rest narrow a list of payments
 * more finely than a table of totals has any use for.
 */
const OVERVIEW_KEYS: readonly string[] = ['from', 'to', 'provider', 'status', 'search'];

const FILTER_FIELDS = listFilters(REPORTS.payments).filter((field) =>
  OVERVIEW_KEYS.includes(field.key),
);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/** `/admin/payments`: the tiles and the period table. */
export function AdminPaymentsPage(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  const [group, setGroup] = useState<SummaryGroup>('month');

  const monthly = useMonthlyTotals();
  const summary = useAdminPaymentSummary(group, filters);

  const totals = useMemo(() => dashboardTotals(monthly.data ?? []), [monthly.data]);

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
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            label="Filter the totals"
          />
        }
      />
    </Page>
  );
}
