/**
 * `/admin/members` — the filtered, sortable, exportable member list.
 *
 * Filters live in the URL, so a filtered list is a link an administrator can
 * bookmark or send to a colleague, and the export buttons point at the same
 * query the table is showing.  The filters are the members report's own, drawn
 * by the shared `FilterBar` from `REPORTS.members`.
 *
 * The column chooser governs the table and both downloads together: the table
 * shows the members report's chosen columns, in the report's order, and a saved
 * set of columns applies to the screen as it does to the files.  It opens on the
 * report's default columns.  Name, Email, DART, Expires, Joined, and Profile updated
 * sort on the server; the other headings do not sort, and carry no arrow.  On a
 * narrow screen the optional columns go first, then Email, then DART, while the
 * name, the membership status, and the expiry stay.
 *
 * The list hides deactivated accounts until **Include deactivated** is ticked.
 * That switch is the list's own: the report never lists a deactivated account,
 * so the export links leave it out.
 *
 * A DART leader reads the same list and downloads the same report, but the
 * member record is the account administrator's: for a leader there is no
 * **New member** button, and a name opens the member check instead.
 */
import { useMemo } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useDarts } from '@/portal/api/queries';
import type { MemberRow, ReportColumn } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import {
  ACCOUNT_KIND_LABELS,
  MEMBERSHIP_STATUS_LABELS,
  certificateLabel,
  medicalLabel,
} from '@/portal/choices';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { FilterBar, clearedValues } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { MembershipDot, PilotMark } from '@/portal/components/StatusChip';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { hasAnyRole } from '@/portal/nav';
import { reportExportUrl } from '@/portal/reports/api';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterField, FilterValues } from '@/portal/reports/types';
import { useMembers } from './api';

const PAGE_SIZE = 25;

/** The order the list opens on, which the server also falls back to. */
const DEFAULT_ORDERING = 'name';

/** The list's switch for deactivated accounts, which the report never lists. */
const INCLUDE_INACTIVE = 'include_inactive';

const INCLUDE_INACTIVE_FIELD: FilterField = {
  key: INCLUDE_INACTIVE,
  label: 'Include deactivated',
  kind: 'toggle',
  hint: 'List the accounts that have been deactivated as well.',
};

/**
 * The filters the list draws: the members report's, less any a subscription
 * alone offers, and then the list's own Include deactivated switch.
 */
const FILTER_FIELDS = [...listFilters(REPORTS.members), INCLUDE_INACTIVE_FIELD];
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/**
 * Where a name in the list leads: the member record, or the member check for a leader.
 * The member check never shows a deactivated account, so a leader's link for one is null.
 */
function memberHref(row: MemberRow, isAccountAdmin: boolean): string | null {
  if (isAccountAdmin) return `/admin/members/${row.user_id}`;
  return row.is_active ? `/leader?member=${row.user_id}` : null;
}

function MemberName({
  row,
  isAccountAdmin,
}: {
  row: MemberRow;
  isAccountAdmin: boolean;
}): JSX.Element {
  const href = memberHref(row, isAccountAdmin);
  return (
    <>
      {href === null ? row.name : <Link to={href}>{row.name}</Link>}
      {row.is_active ? null : <small className="muted"> · account deactivated</small>}
    </>
  );
}

/**
 * The expiry cell: the date, **Never** for a lifetime member, and **Friend** for a
 * friend, who pays no dues and so has no date.
 */
function ExpiryText({ row }: { row: MemberRow }): JSX.Element {
  if (row.membership.status === 'friend') {
    return <span className="muted">{MEMBERSHIP_STATUS_LABELS.friend}</span>;
  }
  if (row.membership.is_lifetime) return <>Never</>;
  return <DateText value={row.membership.expires_on} />;
}

/**
 * The kind the report prints: Friend for anybody whose membership reads friend, which
 * takes in a member whose change to friend has come; otherwise the account's kind.
 */
function kindLabel(row: MemberRow): string {
  return row.membership.status === 'friend'
    ? ACCOUNT_KIND_LABELS.friend
    : ACCOUNT_KIND_LABELS[row.kind];
}

/**
 * The certificate cell as the report prints it: blank for no certificate, and the
 * airline transport pilot certificate as ATP, which keeps the column narrow.
 */
function certificateText(certificate: MemberRow['pilot_certificate_type']): string {
  if (certificate === 'none') return '';
  return certificate === 'atp' ? 'ATP' : certificateLabel(certificate);
}

/** Yes or No for a pilot's instrument rating, blank for somebody who is no pilot. */
function instrumentText(instrument: boolean | null): string {
  if (instrument === null) return '';
  return instrument ? 'Yes' : 'No';
}

/**
 * The report's default columns, which the table shows while the registry loads or if it
 * cannot be read, so the table and the downloads still agree.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'phone', label: 'Phone', default: true },
  { key: 'dart', label: 'DART', default: true },
  { key: 'status', label: 'Status', default: true },
  { key: 'kind', label: 'Kind', default: true },
  { key: 'expires_on', label: 'Expires', default: true },
  { key: 'certificate', label: 'Certificate', default: true },
  { key: 'medical_type', label: 'Medical', default: true },
  { key: 'medical_expiration', label: 'Medical expires', default: true },
  { key: 'aircraft', label: 'Aircraft', default: true },
];

/**
 * How each members report column draws.  On a narrow screen the default columns go in
 * a stated order: Email, then DART, then Phone, Kind, and Aircraft, so a laptop keeps the
 * pilot columns, then Medical, Certificate, and Medical expires.  The name, the
 * membership status, and the expiry never go, and neither does a column somebody ticked
 * beyond the defaults: the table scrolls instead.
 */
function memberCells(isAccountAdmin: boolean): Record<string, ReportCell<MemberRow>> {
  return {
    name: {
      ordering: 'name',
      isIdentity: true,
      minWidth: '12rem',
      render: (row) => <MemberName row={row} isAccountAdmin={isAccountAdmin} />,
    },
    email: {
      ordering: 'email',
      minWidth: '14rem',
      dropOrder: 1,
      render: (row) => <a href={`mailto:${row.email}`}>{row.email}</a>,
    },
    phone: { width: '8.5rem', noWrap: true, dropOrder: 3, render: (row) => row.phone },
    dart: {
      ordering: 'dart',
      minWidth: '9rem',
      dropOrder: 2,
      render: (row) => row.dart ?? 'Unaffiliated',
    },
    status: {
      width: '7rem',
      keepInSight: true,
      render: (row) => (
        <>
          {/* The word says the state; the dot beside it adds the amber of an expiry
              that is close, which the Expires column dates. */}
          <span aria-hidden="true">
            <MembershipDot membership={row.membership} />
          </span>{' '}
          {MEMBERSHIP_STATUS_LABELS[row.membership.status]}
        </>
      ),
    },
    kind: { width: '6rem', dropOrder: 4, render: kindLabel },
    plan: { width: '7rem', render: (row) => row.membership.plan ?? '' },
    expires_on: {
      ordering: 'expires_on',
      width: '8rem',
      keepInSight: true,
      render: (row) => <ExpiryText row={row} />,
    },
    certificate: {
      width: '7rem',
      dropOrder: 7,
      render: (row) => certificateText(row.pilot_certificate_type),
    },
    certificate_number: {
      width: '8rem',
      noWrap: true,
      render: (row) => row.certificate_number,
    },
    instrument: {
      width: '7rem',
      render: (row) => instrumentText(row.instrument),
    },
    medical_type: {
      width: '7rem',
      dropOrder: 6,
      render: (row) => (row.medical_type === 'none' ? '' : medicalLabel(row.medical_type)),
    },
    medical_expiration: {
      width: '9.5rem',
      dropOrder: 8,
      render: (row) => (
        <>
          <PilotMark
            isPilot={row.pilot_certificate_type !== 'none'}
            isCurrent={row.medical_is_current}
          />{' '}
          <DateText value={row.medical_expiration} placeholder="" />
        </>
      ),
    },
    aircraft: { minWidth: '7rem', dropOrder: 5, render: (row) => row.aircraft.join(' ') },
    home_airport: { width: '6.5rem', render: (row) => row.home_airport },
    secondary_airport: {
      width: '6.5rem',
      render: (row) => row.secondary_airport,
    },
    city: { minWidth: '7rem', render: (row) => row.city },
    state: { width: '4.5rem', render: (row) => row.state },
    county: { minWidth: '8rem', render: (row) => row.county },
    ham_callsign: { width: '6.5rem', render: (row) => row.ham_callsign },
    joined_on: {
      ordering: 'joined',
      width: '8rem',
      render: (row) => <DateText value={row.joined_on} />,
    },
    member_since: {
      width: '8rem',
      render: (row) => <DateText value={row.member_since} />,
    },
    profile_updated: {
      ordering: 'updated',
      width: '8.5rem',
      render: (row) => <DateText value={row.profile_updated_at} />,
    },
  };
}

/** `/admin/members` page: the filtered, sortable, exportable member list. */
export function MembersListPage(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  // The order and the page live in the address beside the filters.
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage, sort, setSort: handleSortChange } = position;
  const { roles } = useAuth();
  const isAccountAdmin = hasAnyRole(roles, ['account_admin']);

  const darts = useDarts();
  const dartOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
    }),
    [darts.data],
  );
  const members = useMembers({ filters: { ...filters, ordering }, page, page_size: PAGE_SIZE });
  useFirstPageWhenMissing(position, members.error);

  const choice = useColumnChoice('members', FALLBACK_COLUMNS);
  const cells = useMemo(() => memberCells(isAccountAdmin), [isAccountAdmin]);
  const columns = useMemo(
    () => reportTableColumns(choice.tableColumns, choice.tableChosen, cells, true),
    [choice.tableColumns, choice.tableChosen, cells],
  );
  const { [INCLUDE_INACTIVE]: _listOnly, ...reportFilters } = filters;
  const exportParams = { ...reportFilters, ordering, columns: choice.chosen };

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
  };

  const handleReset = (): void => {
    setFilters(clearedValues(FILTER_FIELDS, filters));
  };

  const count = members.data?.count ?? 0;
  const rows = members.data?.results ?? [];

  return (
    <Page
      title="Members"
      lede="Every member and friend of CalDART, with their membership, certificate, and medical currency."
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
          label="Members"
          filters={
            <FilterBar
              fields={FILTER_FIELDS}
              values={filters}
              onChange={handleFilterChange}
              options={dartOptions}
              label="Filter members"
            />
          }
          tools={<ColumnTools choice={choice} />}
          exportCsvUrl={reportExportUrl('members', 'csv', exportParams)}
          exportPdfUrl={reportExportUrl('members', 'pdf', exportParams)}
          isLoading={members.isPending}
          onSortChange={handleSortChange}
          sort={sort}
          emptyTitle="No members match these filters"
          emptyDescription="Widen the search, or reset the filters to see everyone."
          emptyAction={
            <Button variant="quiet" onClick={handleReset}>
              Reset filters
            </Button>
          }
          pagination={{
            page,
            pageSize: PAGE_SIZE,
            count,
            onPageChange: setPage,
            label: 'Member pages',
          }}
        />

        {members.isError ? (
          <p role="alert" className="field__error">
            The member list could not be loaded.
          </p>
        ) : null}
      </Card>
    </Page>
  );
}
