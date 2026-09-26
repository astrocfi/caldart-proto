/**
 * `/admin/payments/renewals` — the standing authorities people have given
 * CalDART, automatic renewals and recurring donations alike, and the charges
 * scheduled against them.
 *
 * Two tables: the mandates, which is where a support call is answered and
 * where one can be turned off on a member's behalf, and the recent attempts,
 * which is where "why was I not charged?" is answered.  The mandates narrow by
 * status and by kind.  Turning a mandate off asks first, because the member is
 * emailed about it.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type {
  MandateKind,
  MandateStatus,
  RenewalAttempt,
  RenewalMandate,
  RenewalOutcome,
} from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { useDebounced } from '@/portal/components/useDebounced';
import { CADENCE_LABELS } from '@/portal/features/payments/labels';
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

const STATUSES: MandateStatus[] = ['active', 'pending', 'paused', 'canceled'];
const KINDS: MandateKind[] = ['renewal', 'both', 'contribution'];
const OUTCOMES: RenewalOutcome[] = ['scheduled', 'succeeded', 'failed', 'skipped'];

/** A mandate can still be turned off while it is pending, active or paused. */
export function isCancelable(mandate: RenewalMandate): boolean {
  return mandate.status !== 'canceled';
}

interface PagerProps {
  label: string;
  page: number;
  count: number;
  onPageChange: (page: number) => void;
}

/** Previous/Next for one of the tab's two tables; nothing when a page holds it all. */
function Pager({ label, page, count, onPageChange }: PagerProps): JSX.Element | null {
  const lastPage = Math.max(1, Math.ceil(count / RENEWAL_PAGE_SIZE));
  if (lastPage === 1) return null;
  return (
    <nav className="pager" aria-label={label}>
      <Button variant="quiet" small disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Previous
      </Button>
      <span className="muted pager__status" aria-live="polite">
        Page {page} of {lastPage}
      </span>
      <Button
        variant="quiet"
        small
        disabled={page >= lastPage}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </Button>
    </nav>
  );
}

/** The Renewals tab of the finance area. */
export function RenewalsPage(): JSX.Element {
  const toast = useToast();

  const [status, setStatus] = useState<MandateStatus | ''>('');
  const [kind, setKind] = useState<MandateKind | ''>('');
  const [term, setTerm] = useState('');
  const [outcome, setOutcome] = useState<RenewalOutcome | ''>('');
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [mandatePage, setMandatePage] = useState(1);
  const [attemptPage, setAttemptPage] = useState(1);

  const search = useDebounced(term.trim());
  const mandates = useRenewalMandates({ status, kind, search }, mandatePage);
  const attempts = useRenewalAttempts(outcome, attemptPage);
  const cancel = useCancelMandate();

  const handleCancel = (mandate: RenewalMandate): void => {
    cancel.mutate(mandate.id, {
      onSuccess: () => {
        setConfirmingId(null);
        toast.show(
          `${MANDATE_KIND_LABELS[mandate.kind]} is off for ${mandate.user_name}.`,
          'success',
        );
      },
      onError: (error) => {
        toast.show(
          error instanceof Error ? error.message : 'That renewal could not be turned off.',
          'error',
        );
      },
    });
  };

  const mandateColumns: Column<RenewalMandate>[] = [
    {
      key: 'user_name',
      header: 'Member',
      render: (row) => (
        <>
          {row.user_name}
          <span className="muted"> · {row.user_email}</span>
        </>
      ),
      sortValue: (row) => row.user_name,
    },
    {
      key: 'kind',
      header: 'Kind',
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
    {
      key: 'plan_name',
      header: 'Plan',
      render: (row) => row.plan_name ?? <span className="muted">&mdash;</span>,
    },
    {
      key: 'amount_cents',
      header: 'Next charge',
      numeric: true,
      render: (row) => <Money cents={row.amount_cents} />,
      sortValue: (row) => row.amount_cents,
    },
    {
      key: 'next_charge_on',
      header: 'Due',
      render: (row) => <DateText value={row.next_charge_on} />,
      sortValue: (row) => row.next_charge_on,
    },
    { key: 'method_label', header: 'Method', render: (row) => row.method_label },
    {
      key: 'status',
      header: 'Status',
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
    {
      key: 'actions',
      header: 'Actions',
      sortable: false,
      render: (row) => {
        if (!isCancelable(row)) return <span className="muted">Off</span>;
        if (confirmingId !== row.id) {
          return (
            <Button variant="quiet" small onClick={() => setConfirmingId(row.id)}>
              Turn off
            </Button>
          );
        }
        return (
          <span className="cluster">
            <Button
              variant="danger"
              small
              disabled={cancel.isPending}
              onClick={() => handleCancel(row)}
            >
              Yes, turn it off
            </Button>
            <Button variant="quiet" small onClick={() => setConfirmingId(null)}>
              Keep it
            </Button>
          </span>
        );
      },
    },
  ];

  const attemptColumns: Column<RenewalAttempt>[] = [
    {
      key: 'scheduled_on',
      header: 'Scheduled',
      render: (row) => <DateText value={row.scheduled_on} />,
      sortValue: (row) => row.scheduled_on,
    },
    { key: 'user_name', header: 'Member', render: (row) => row.user_name },
    {
      key: 'outcome',
      header: 'Outcome',
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
      render: (row) => <DateText value={row.attempted_at} withTime />,
      sortValue: (row) => row.attempted_at,
    },
    {
      key: 'error',
      header: 'Reason',
      sortable: false,
      render: (row) => (row.error === '' ? <span className="muted">&mdash;</span> : row.error),
    },
  ];

  const mandateFilters = (
    <div className="payment-filters">
      <Field label="Auto-renewal status">
        {(props) => (
          <select
            {...props}
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as MandateStatus | '');
              setMandatePage(1);
            }}
          >
            <option value="">Any status</option>
            {STATUSES.map((option) => (
              <option key={option} value={option}>
                {MANDATE_STATUS_LABELS[option]}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Kind">
        {(props) => (
          <select
            {...props}
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as MandateKind | '');
              setMandatePage(1);
            }}
          >
            <option value="">Any kind</option>
            {KINDS.map((option) => (
              <option key={option} value={option}>
                {MANDATE_KIND_LABELS[option]}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Search">
        {(props) => (
          <input
            {...props}
            type="search"
            placeholder="Name, email, or the saved method"
            value={term}
            onChange={(event) => {
              setTerm(event.target.value);
              setMandatePage(1);
            }}
          />
        )}
      </Field>
    </div>
  );

  const attemptFilters = (
    <div className="payment-filters">
      <Field label="Outcome">
        {(props) => (
          <select
            {...props}
            value={outcome}
            onChange={(event) => {
              setOutcome(event.target.value as RenewalOutcome | '');
              setAttemptPage(1);
            }}
          >
            <option value="">Any outcome</option>
            {OUTCOMES.map((option) => (
              <option key={option} value={option}>
                {RENEWAL_OUTCOME_LABELS[option]}
              </option>
            ))}
          </select>
        )}
      </Field>
    </div>
  );

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
          columns={mandateColumns}
          rows={mandateRows}
          rowKey={(row) => row.id}
          caption={`${mandateCount} renewal${mandateCount === 1 ? '' : 's'}`}
          filters={mandateFilters}
          isLoading={mandates.isPending}
          emptyTitle="No renewals match"
          emptyDescription="Clear the status and kind filters, or search for a different member."
        />
        {mandates.isError ? (
          <p role="alert" className="field__error">
            The renewals could not be loaded.
          </p>
        ) : null}
        <Pager
          label="Renewal pages"
          page={mandatePage}
          count={mandateCount}
          onPageChange={(next) => setMandatePage(next)}
        />
      </section>

      <section className="stack">
        <h2 className="period-table__title">Recent charges</h2>
        <DataTable
          columns={attemptColumns}
          rows={attemptRows}
          rowKey={(row) => row.id}
          caption={`${attemptCount} attempt${attemptCount === 1 ? '' : 's'}`}
          filters={attemptFilters}
          isLoading={attempts.isPending}
          emptyTitle="No renewal charges yet"
          emptyDescription="The scan schedules a charge a fortnight before it is taken."
        />
        {attempts.isError ? (
          <p role="alert" className="field__error">
            The renewal charges could not be loaded.
          </p>
        ) : null}
        <Pager
          label="Renewal charge pages"
          page={attemptPage}
          count={attemptCount}
          onPageChange={(next) => setAttemptPage(next)}
        />
      </section>
    </Page>
  );
}
