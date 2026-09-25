/**
 * `/admin/members` — the filtered, sortable, exportable member list.
 *
 * Filters live in the URL, so a filtered list is a link an administrator can
 * bookmark or send to a colleague, and the export buttons point at the same
 * query the table is showing.  The filters are the members report's own, drawn
 * by the shared `FilterBar` from `REPORTS.members`.
 *
 * Five columns, kept narrow enough to scan: whether the member may fly, who
 * they are, their team, when their membership runs out, and how to reach them.
 * Every column maps onto an `?ordering=` value the API accepts, Pilot included:
 * the server ranks a current medical ahead of a lapsed one ahead of somebody
 * who is not a pilot, which is the order the column's marks read in.
 *
 * The membership report carries far more than those five, so the column chooser
 * drives the two export links rather than the table: the screen stays scannable
 * while the CSV and the PDF carry whatever the administrator asked for.
 *
 * A DART leader reads the same list and downloads the same report, but the
 * member record is the account administrator's: for a leader there is no
 * **New member** button, and a name opens the member check instead.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useDarts } from '@/portal/api/queries';
import type { MemberRow } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import type { Column, SortDirection } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { FilterBar } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import { MembershipDot, PilotMark } from '@/portal/components/StatusChip';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import { hasAnyRole } from '@/portal/nav';
import { reportExportUrl, useReportColumns } from '@/portal/reports/api';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterValues } from '@/portal/reports/types';
import { useMembers } from './api';

const PAGE_SIZE = 25;

/** The filters the list draws: the members report's, less any a subscription alone offers. */
const FILTER_FIELDS = listFilters(REPORTS.members);

/** The table's sort, which the URL keeps beside the filters. */
const ORDERING = 'ordering';

/** Every query parameter the list keeps in the URL, the page number aside. */
const URL_KEYS = [...FILTER_FIELDS.map((field) => field.key), ORDERING];

function ordering(value: string): { key: string; direction: SortDirection } | undefined {
  if (!value) return undefined;
  const descending = value.startsWith('-');
  return {
    key: descending ? value.slice(1) : value,
    direction: descending ? 'desc' : 'asc',
  };
}

/** Where a name in the list leads: the member record, or the member check for a leader. */
function memberHref(row: MemberRow, isAccountAdmin: boolean): string {
  return isAccountAdmin ? `/admin/members/${row.user_id}` : `/leader?member=${row.user_id}`;
}

function memberColumns(isAccountAdmin: boolean): Column<MemberRow>[] {
  return [
    {
      key: 'pilot',
      header: 'Pilot',
      width: '4.25rem',
      render: (row) => (
        <PilotMark
          isPilot={row.pilot_certificate_type !== 'none'}
          isCurrent={row.medical_is_current}
        />
      ),
    },
    {
      key: 'name',
      header: 'Name',
      width: '22%',
      render: (row) => (
        <>
          <Link to={memberHref(row, isAccountAdmin)}>{row.name}</Link>
          {row.is_active ? null : <small className="muted"> · account deactivated</small>}
        </>
      ),
    },
    {
      key: 'dart',
      header: 'DART',
      width: '18%',
      render: (row) => row.dart ?? 'Unaffiliated',
    },
    {
      key: 'expires_on',
      header: 'Membership Exp.',
      width: '11rem',
      render: (row) => (
        <>
          <MembershipDot membership={row.membership} />{' '}
          {row.membership.is_lifetime ? 'Never' : <DateText value={row.membership.expires_on} />}
        </>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      render: (row) => <a href={`mailto:${row.email}`}>{row.email}</a>,
    },
  ];
}

/** `/admin/members` page: the filtered, sortable, exportable member list. */
export function MembersListPage(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useUrlFilters(URL_KEYS);
  const page = Number(params.get('page') ?? '1') || 1;
  const { roles } = useAuth();
  const isAccountAdmin = hasAnyRole(roles, ['account_admin']);

  const darts = useDarts();
  const dartOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
    }),
    [darts.data],
  );
  const members = useMembers({ filters, page, page_size: PAGE_SIZE });

  const columns = useMemo(() => memberColumns(isAccountAdmin), [isAccountAdmin]);

  const registry = useReportColumns('members');
  const reportColumns = useMemo(() => registry.data ?? [], [registry.data]);
  // Null means "whatever the registry calls default": the chooser has not been
  // touched, so it must follow a registry that is still loading.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const chosenKeys = chosen ?? defaultColumnKeys(reportColumns);
  const exportParams = { ...filters, columns: chosenKeys };

  const handleFilterChange = (next: FilterValues) => {
    setFilters(next);
  };

  const handleColumnChange = (next: string[]) => {
    setChosen(next);
  };

  const setPage = (next: number) => {
    const updated = new URLSearchParams(params);
    if (next <= 1) updated.delete('page');
    else updated.set('page', String(next));
    setParams(updated);
  };

  const count = members.data?.count ?? 0;
  const rows = members.data?.results ?? [];
  const firstRow = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRow = (page - 1) * PAGE_SIZE + rows.length;

  return (
    <Page
      title="Members"
      eyebrow="Administration"
      lede="Everyone with a CalDART account, with their membership, certificate, and medical currency."
      actions={
        isAccountAdmin ? <ButtonLink to="/admin/members/new">New member</ButtonLink> : undefined
      }
    >
      <Card>
        <DataTable
          singleLine
          columns={columns}
          rows={rows}
          rowKey={(row) => row.user_id}
          caption={
            members.isPending
              ? 'Loading members'
              : `${count} member${count === 1 ? '' : 's'} match these filters`
          }
          filters={
            <>
              <FilterBar
                fields={FILTER_FIELDS}
                values={filters}
                onChange={handleFilterChange}
                options={dartOptions}
                label="Filter members"
              />
              {registry.isError ? (
                <p className="muted">
                  The columns could not be loaded; the downloads carry the default columns.
                </p>
              ) : reportColumns.length > 0 ? (
                <ColumnChooser
                  columns={reportColumns}
                  chosen={chosenKeys}
                  onChange={handleColumnChange}
                  legend="Columns to export"
                />
              ) : null}
            </>
          }
          exportCsvUrl={reportExportUrl('members', 'csv', exportParams)}
          exportPdfUrl={reportExportUrl('members', 'pdf', exportParams)}
          isLoading={members.isPending}
          onSortChange={(key, direction) =>
            setFilters({ ...filters, [ORDERING]: direction === 'desc' ? `-${key}` : key })
          }
          initialSort={ordering(filters[ORDERING] ?? '')}
          emptyTitle="No members match these filters"
          emptyDescription="Widen the search, or clear the filters to see everyone."
        />

        {members.isError ? (
          <p role="alert" className="field__error">
            The member list could not be loaded.
          </p>
        ) : null}

        {count > PAGE_SIZE ? (
          <div className="cluster card__footer">
            <p className="muted">
              Showing {firstRow}–{lastRow} of {count}
            </p>
            <Button
              variant="quiet"
              small
              disabled={!members.data?.previous}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <Button
              variant="quiet"
              small
              disabled={!members.data?.next}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </Card>
    </Page>
  );
}
