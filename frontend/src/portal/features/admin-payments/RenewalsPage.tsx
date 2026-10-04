/**
 * `/admin/payments/renewals` — the standing authorities people have given
 * CalDART, automatic renewals and recurring donations alike, and the charges
 * scheduled against them.
 *
 * Two tables: the mandates, which is where a support call is answered and
 * where one can be turned off on a member's behalf, and the recent attempts,
 * which is where "why was I not charged?" is answered.  The mandates narrow by
 * status, by kind, and by a search, held in the address like every finance tab's
 * filters, and their column chooser drives the table and the renewals report's CSV
 * and PDF together.  Turning a mandate off asks first, because the member is
 * emailed about it.
 */
import type { JSX } from 'react';

import type {
  MandateKind,
  MandateStatus,
  RenewalAttempt,
  RenewalMandate,
  RenewalOutcome,
  ReportColumn,
} from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import { CADENCE_LABELS } from '@/portal/features/payments/labels';
import { reportExportUrl } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import type { FilterField } from '@/portal/reports/types';
import { FinanceTabs } from './FinanceTabs';
import { MANDATE_KIND_LABELS } from './labels';
import {
  MANDATE_STATUS_LABELS,
  MANDATE_STATUS_TONES,
  RENEWAL_OUTCOME_LABELS,
  RENEWAL_OUTCOME_TONES,
  RENEWAL_PAGE_SIZE,
  useCancelMandate,
  useRenewalAttempts,
  useRenewalMandates,
} from './reports-api';
import './admin-payments.css';

/**
 * The report's default columns, which the table shows while the registry loads or if it
 * cannot be read, so the table and the downloads still agree.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Member', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'kind', label: 'Kind', default: true },
  { key: 'plan', label: 'Plan', default: true },
  { key: 'amount', label: 'Next charge', default: true },
  { key: 'next_charge_on', label: 'Due', default: true },
  { key: 'method', label: 'Method', default: true },
  { key: 'status', label: 'Status', default: true },
];

const OUTCOMES: RenewalOutcome[] = ['scheduled', 'succeeded', 'failed', 'skipped'];

/** A mandate can still be turned off while it is pending, active or paused. */
export function isCancelable(mandate: RenewalMandate): boolean {
  return mandate.status !== 'canceled';
}

/** The mandates' filters, the renewals report's own. */
const MANDATE_FILTERS = listFilters(REPORTS.renewals);
const MANDATE_FILTER_KEYS = MANDATE_FILTERS.map((field) => field.key);

/**
 * The query parameters the two tables keep their pages in, each its own, so paging one
 * table never moves the other.
 */
const MANDATES_PAGE = 'renewals_page';
const ATTEMPTS_PAGE = 'attempts_page';

/** The attempts table's one filter, which is the tab's own rather than a report's. */
const ATTEMPT_FILTERS: FilterField[] = [
  {
    key: 'outcome',
    label: 'Outcome',
    kind: 'select',
    placeholder: 'Any outcome',
    options: OUTCOMES.map((value) => ({ value, label: RENEWAL_OUTCOME_LABELS[value] })),
  },
];

/** A page number from the address: a whole number from 1, else 1. */
function pageOf(value: string | undefined): number {
  const page = Number(value);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

/**
 * How the mandates table draws each report column, and its width.  The member
 * identifies a row and stays pinned when the table scrolls; the amount and the status
 * stay in sight on a phone, and the rest drop, the least needed first.
 */
const MANDATE_CELLS: Record<string, ReportCell<RenewalMandate>> = {
  name: {
    minWidth: '10rem',
    isIdentity: true,
    render: (row) => row.user_name,
    sortValue: (row) => row.user_name,
  },
  email: {
    minWidth: '12rem',
    dropOrder: 1,
    render: (row) => row.user_email,
    sortValue: (row) => row.user_email,
  },
  kind: {
    minWidth: '11rem',
    dropOrder: 3,
    render: (row) => (
      <>
        {MANDATE_KIND_LABELS[row.kind]}
        {row.kind === 'contribution' ? (
          <span className="muted"> · {CADENCE_LABELS[row.cadence]}</span>
        ) : null}
      </>
    ),
    sortValue: (row) => row.kind,
  },
  cadence: {
    width: '6.5rem',
    dropOrder: 2,
    render: (row) => CADENCE_LABELS[row.cadence],
    sortValue: (row) => row.cadence,
  },
  plan: {
    width: '7rem',
    dropOrder: 2,
    render: (row) => row.plan_name ?? <span className="muted">&mdash;</span>,
    sortValue: (row) => row.plan_name ?? '',
  },
  amount: {
    width: '7.5rem',
    numeric: true,
    keepInSight: true,
    render: (row) => <Money cents={row.amount_cents} />,
    sortValue: (row) => row.amount_cents,
  },
  next_charge_on: {
    width: '7rem',
    noWrap: true,
    dropOrder: 4,
    render: (row) => <DateText value={row.next_charge_on} />,
    sortValue: (row) => row.next_charge_on,
  },
  method: { minWidth: '10rem', dropOrder: 1, render: (row) => row.method_label },
  status: {
    width: '9rem',
    narrowWidth: '7rem',
    keepInSight: true,
    wrap: true,
    render: (row) => (
      <>
        <StatusChip
          tone={MANDATE_STATUS_TONES[row.status]}
          label={MANDATE_STATUS_LABELS[row.status]}
        />
        {row.last_error === '' ? null : <p className="muted">{row.last_error}</p>}
      </>
    ),
    sortValue: (row) => row.status,
  },
  failures: {
    width: '7rem',
    numeric: true,
    dropOrder: 2,
    render: (row) => row.failure_count,
    sortValue: (row) => row.failure_count,
  },
  started_on: {
    width: '7rem',
    noWrap: true,
    dropOrder: 2,
    render: (row) => <DateText value={row.created_at} />,
    sortValue: (row) => row.created_at,
  },
};

/** The Renewals tab of the finance area. */
export function RenewalsPage(): JSX.Element {
  const toast = useToast();

  const [mandateValues, setMandateValues] = useUrlFilters([...MANDATE_FILTER_KEYS, MANDATES_PAGE]);
  const { [MANDATES_PAGE]: mandatePageValue, ...filters } = mandateValues;
  const [attemptValues, setAttemptValues] = useUrlFilters(['outcome', ATTEMPTS_PAGE]);
  const choice = useColumnChoice('renewals', FALLBACK_COLUMNS);

  const mandatePage = pageOf(mandatePageValue);
  const attemptPage = pageOf(attemptValues[ATTEMPTS_PAGE]);
  const outcome = (attemptValues.outcome ?? '') as RenewalOutcome | '';
  const mandates = useRenewalMandates(
    {
      status: (filters.status ?? '') as MandateStatus | '',
      kind: (filters.kind ?? '') as MandateKind | '',
      search: (filters.search ?? '').trim(),
    },
    mandatePage,
  );
  const attempts = useRenewalAttempts(outcome, attemptPage);
  const cancel = useCancelMandate();
  const exportParams = { ...filters, columns: choice.chosen };

  // A change of filter returns the renewals to their first page; the charges keep theirs.
  const setFilters = (next: Record<string, string>): void => {
    setMandateValues({ ...next, [MANDATES_PAGE]: '' });
  };
  const setMandatePage = (next: number): void => {
    setMandateValues({ ...filters, [MANDATES_PAGE]: next > 1 ? String(next) : '' });
  };
  const setAttemptPage = (next: number): void => {
    setAttemptValues({ outcome, [ATTEMPTS_PAGE]: next > 1 ? String(next) : '' });
  };

  // Rejects when the request fails, so the confirmation stays open.
  const handleCancel = (mandate: RenewalMandate): Promise<unknown> =>
    cancel.mutateAsync(mandate.id).then(
      () =>
        toast.show(
          `${MANDATE_KIND_LABELS[mandate.kind]} is off for ${mandate.user_name}.`,
          'success',
        ),
      (error: unknown) => {
        toast.show(
          error instanceof Error ? error.message : 'That renewal could not be turned off.',
          'error',
        );
        throw error;
      },
    );

  const mandateColumns: Column<RenewalMandate>[] = [
    ...reportTableColumns(choice.tableColumns, choice.tableChosen, MANDATE_CELLS, false),
    {
      key: 'actions',
      header: 'Actions',
      isActions: true,
      width: '13rem',
      render: (row) => {
        if (!isCancelable(row)) return <span className="muted">Off</span>;
        return (
          <ConfirmButton
            label="Turn off"
            variant="quiet"
            small
            choices={[
              { label: 'Turn it off', variant: 'danger', onChoose: () => handleCancel(row) },
            ]}
          >
            <p>
              Turn off {MANDATE_KIND_LABELS[row.kind].toLowerCase()} for {row.user_name}? They are
              emailed that it is off.
            </p>
          </ConfirmButton>
        );
      },
    },
  ];

  const attemptColumns: Column<RenewalAttempt>[] = [
    {
      key: 'scheduled_on',
      header: 'Scheduled',
      width: '7rem',
      noWrap: true,
      render: (row) => <DateText value={row.scheduled_on} />,
      sortValue: (row) => row.scheduled_on,
    },
    {
      key: 'user_name',
      header: 'Member',
      minWidth: '10rem',
      isIdentity: true,
      render: (row) => row.user_name,
      sortValue: (row) => row.user_name,
    },
    {
      key: 'outcome',
      header: 'Outcome',
      width: '8rem',
      keepInSight: true,
      render: (row) => (
        <StatusChip
          tone={RENEWAL_OUTCOME_TONES[row.outcome]}
          label={RENEWAL_OUTCOME_LABELS[row.outcome]}
        />
      ),
      sortValue: (row) => row.outcome,
    },
    {
      key: 'attempted_at',
      header: 'Tried',
      width: '13rem',
      noWrap: true,
      dropOrder: 1,
      render: (row) => <DateText value={row.attempted_at} withTime />,
      sortValue: (row) => row.attempted_at,
    },
    {
      key: 'error',
      header: 'Reason',
      minWidth: '12rem',
      wrap: true,
      dropOrder: 2,
      render: (row) => (row.error === '' ? <span className="muted">&mdash;</span> : row.error),
    },
  ];

  const mandateRows = mandates.data?.results ?? [];
  const attemptRows = attempts.data?.results ?? [];
  const mandateCount = mandates.data?.count ?? 0;
  const attemptCount = attempts.data?.count ?? 0;

  return (
    <Page
      title="Renewals"
      eyebrow="Payments"
      lede="Who has asked CalDART to renew their membership, to give on a schedule, or both, and how those charges went."
    >
      <FinanceTabs />

      <section className="stack">
        <h2 className="period-table__title">Automatic renewals and recurring donations</h2>
        <DataTable
          singleLine
          columns={mandateColumns}
          rows={mandateRows}
          rowKey={(row) => row.id}
          caption={`${mandateCount} renewal${mandateCount === 1 ? '' : 's'}`}
          filters={
            <FilterBar
              fields={MANDATE_FILTERS}
              values={filters}
              onChange={(next) => setFilters(next)}
              label="Filter renewals"
            />
          }
          tools={<ColumnTools choice={choice} />}
          exportCsvUrl={reportExportUrl('renewals', 'csv', exportParams)}
          exportPdfUrl={reportExportUrl('renewals', 'pdf', exportParams)}
          isLoading={mandates.isPending}
          emptyTitle="No renewals match"
          emptyDescription="Reset the filters, or search for a different member."
          emptyAction={
            <Button
              variant="secondary"
              onClick={() => setFilters(clearedValues(MANDATE_FILTERS, filters))}
            >
              Reset filters
            </Button>
          }
          pagination={{
            page: mandatePage,
            pageSize: RENEWAL_PAGE_SIZE,
            count: mandateCount,
            onPageChange: setMandatePage,
            label: 'Renewal pages',
          }}
        />
        {mandates.isError ? (
          <p role="alert" className="field__error">
            The renewals could not be loaded.
          </p>
        ) : null}
      </section>

      <section className="stack">
        <h2 className="period-table__title">Recent charges</h2>
        <DataTable
          singleLine
          columns={attemptColumns}
          rows={attemptRows}
          rowKey={(row) => row.id}
          caption={`${attemptCount} attempt${attemptCount === 1 ? '' : 's'}`}
          filters={
            <FilterBar
              fields={ATTEMPT_FILTERS}
              values={{ outcome }}
              onChange={(next) => setAttemptValues({ outcome: next.outcome ?? '' })}
              label="Filter renewal charges"
            />
          }
          isLoading={attempts.isPending}
          emptyTitle="No renewal charges yet"
          emptyDescription="The scan schedules a charge a fortnight before it is taken."
          pagination={{
            page: attemptPage,
            pageSize: RENEWAL_PAGE_SIZE,
            count: attemptCount,
            onPageChange: setAttemptPage,
            label: 'Renewal charge pages',
          }}
        />
        {attempts.isError ? (
          <p role="alert" className="field__error">
            The renewal charges could not be loaded.
          </p>
        ) : null}
      </section>
    </Page>
  );
}
