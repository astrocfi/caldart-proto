/**
 * `/admin/members` — the filtered, sortable, exportable member list.
 *
 * Filters live in the URL, so a filtered list is a link an administrator can
 * bookmark or send to a colleague, and the export buttons point at the same
 * query the table is showing.
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
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useDarts } from '@/portal/api/queries';
import type { MemberRow } from '@/portal/api/types';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import type { Column, SortDirection } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { MembershipDot, PilotMark } from '@/portal/components/StatusChip';
import { MembersFilterBar } from './MembersFilterBar';
import { exportUrl, useMemberReportColumns, useMembers } from './api';
import type { MemberFilters } from './types';
import { EMPTY_FILTERS, FILTER_KEYS } from './types';

const PAGE_SIZE = 25;

/** Read the filter set out of the query string. */
export function filtersFromParams(params: URLSearchParams): MemberFilters {
  const filters = { ...EMPTY_FILTERS };
  for (const key of FILTER_KEYS) filters[key] = params.get(key) ?? '';
  return filters;
}

function ordering(filters: MemberFilters): { key: string; direction: SortDirection } | undefined {
  if (!filters.ordering) return undefined;
  const descending = filters.ordering.startsWith('-');
  return {
    key: descending ? filters.ordering.slice(1) : filters.ordering,
    direction: descending ? 'desc' : 'asc',
  };
}

function memberColumns(): Column<MemberRow>[] {
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
          <Link to={`/admin/members/${row.user_id}`}>{row.name}</Link>
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
  const filters = useMemo(() => filtersFromParams(params), [params]);
  const page = Number(params.get('page') ?? '1') || 1;

  const darts = useDarts();
  const members = useMembers({ ...filters, page, page_size: PAGE_SIZE });

  const columns = useMemo(memberColumns, []);

  const registry = useMemberReportColumns();
  const reportColumns = useMemo(() => registry.data ?? [], [registry.data]);
  // Null means "whatever the registry calls default": the chooser has not been
  // touched, so it must follow a registry that is still loading.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const chosenKeys = chosen ?? defaultColumnKeys(reportColumns);

  /** Write the filter set back to the URL, always returning to page one. */
  const setFilters = (next: MemberFilters) => {
    const updated = new URLSearchParams();
    for (const key of FILTER_KEYS) {
      if (next[key]) updated.set(key, next[key]);
    }
    setParams(updated);
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
      actions={<ButtonLink to="/admin/members/new">New member</ButtonLink>}
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
              <MembersFilterBar
                value={filters}
                onChange={(next) => setFilters(next)}
                darts={darts.data ?? []}
              />
              <ColumnChooser
                columns={reportColumns}
                chosen={chosenKeys}
                onChange={handleColumnChange}
              />
            </>
          }
          exportCsvUrl={exportUrl('csv', filters, { columns: chosenKeys })}
          exportPdfUrl={exportUrl('pdf', filters, { columns: chosenKeys })}
          isLoading={members.isPending}
          onSortChange={(key, direction) =>
            setFilters({ ...filters, ordering: direction === 'desc' ? `-${key}` : key })
          }
          initialSort={ordering(filters)}
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
