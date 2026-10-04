/**
 * `/admin/users` — find an account and see what it may do.
 *
 * The filters are the shared `FilterBar`, held in the address like every other list:
 * a search, a role, the kind of account, the account status, and whether the address
 * bounces.  The list opens on active accounts, since a deactivated one is rarely what
 * anybody is looking for: the status's blank choice is **Active only**, so **Reset
 * filters** returns to it.
 *
 * The column chooser governs the table and the two downloads together.  The
 * downloads are the CalDART roles report, which has a section for every role but
 * member and lists active accounts only: the links carry the screen's search, role,
 * kind, and Email (bounced or not) filter, never its account status.  On screen a row
 * is an account, so the Role column lists every role it holds.  The report cannot
 * follow two of the screen's choices, Donor under Kind of account (a donor holds no
 * role) and the Member role (the report has no section for it), so while either is
 * chosen the exports and the column chooser are disabled and say why.  Name and Email
 * sort on the server; the other headings do not sort.
 */
import { useMemo } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { AccountKind, AdminUser, ReportColumn, RoleSlug } from '@/portal/api/types';
import { ACCOUNT_KIND_LABELS, ROLE_CHOICES, roleLabel } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { DataTable } from '@/portal/components/DataTable';
import { FilterBar, clearedValues } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { MembershipDot } from '@/portal/components/StatusDot';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { reportExportUrl } from '@/portal/reports/api';
import type { FilterField, Option } from '@/portal/reports/types';
import { useAdminUsers } from './api';

const PAGE_SIZE = 25;

/** The order the list opens on, by surname. */
const DEFAULT_ORDERING = 'last_name';

/** The account status that lists deactivated accounts beside the active ones. */
const ANY_STATUS = 'all';

const KIND_OPTIONS: Option[] = (Object.keys(ACCOUNT_KIND_LABELS) as AccountKind[]).map((kind) => ({
  value: kind,
  label: ACCOUNT_KIND_LABELS[kind],
}));

/** The list's filters, each a query parameter the address keeps. */
const FILTER_FIELDS: FilterField[] = [
  { key: 'search', label: 'Search', kind: 'search', placeholder: 'Name or email' },
  { key: 'role', label: 'Role', kind: 'select', placeholder: 'Any role', options: ROLE_CHOICES },
  {
    key: 'kind',
    label: 'Kind of account',
    kind: 'select',
    placeholder: 'Any kind',
    options: KIND_OPTIONS,
  },
  // Blank is the status the list opens on, so Reset filters comes back to it.
  {
    key: 'is_active',
    label: 'Account status',
    kind: 'select',
    placeholder: 'Active only',
    options: [
      { value: ANY_STATUS, label: 'Active and deactivated' },
      { value: 'false', label: 'Deactivated only' },
    ],
  },
  {
    key: 'email_bounced',
    label: 'Email',
    kind: 'select',
    placeholder: 'Any address',
    options: [
      { value: 'true', label: 'Email bounced' },
      { value: 'false', label: 'Not bounced' },
    ],
  },
];
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

const DONOR_EXPORT_REASON = 'A donor holds no role, so the roles report lists nobody.';
const MEMBER_EXPORT_REASON = 'The roles report has no section for Member, so it lists nobody.';

/**
 * Why the roles report cannot follow the screen's filters, or `undefined` when it can.
 */
function exportDisabledReason(role: string, kind: string): string | undefined {
  if (kind === 'donor') return DONOR_EXPORT_REASON;
  if (role === 'member') return MEMBER_EXPORT_REASON;
  return undefined;
}

/** The API's `is_active` for the status chosen: blank means active only. */
function activeParam(status: string): 'true' | 'false' | '' {
  if (status === ANY_STATUS) return '';
  return status === 'false' ? 'false' : 'true';
}

function displayName(user: AdminUser): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

/** How each roles report column draws for one account. */
const CELLS: Record<string, ReportCell<AdminUser>> = {
  role: {
    minWidth: '10rem',
    dropOrder: 15,
    render: (user) =>
      user.roles.length > 0 ? (
        user.roles.map(roleLabel).join(', ')
      ) : (
        <span className="muted">No role</span>
      ),
  },
  name: {
    ordering: 'last_name',
    isIdentity: true,
    minWidth: '12rem',
    render: (user) => (
      <>
        <Link to={`/admin/users/${user.id}`}>{displayName(user)}</Link>
        {user.is_active ? null : <small className="muted"> · account deactivated</small>}
      </>
    ),
  },
  email: {
    ordering: 'email',
    minWidth: '14rem',
    dropOrder: 20,
    render: (user) => user.email,
  },
  phone: { width: '8.5rem', noWrap: true, dropOrder: 5, render: (user) => user.phone },
  dart: { minWidth: '9rem', dropOrder: 10, render: (user) => user.dart ?? '' },
  kind: { width: '6rem', dropOrder: 4, render: (user) => ACCOUNT_KIND_LABELS[user.kind] },
  membership: {
    width: '8.5rem',
    keepInSight: true,
    render: (user) => <MembershipDot membership={user.membership} />,
  },
  city: { minWidth: '7rem', render: (user) => user.city },
  county: { minWidth: '8rem', render: (user) => user.county },
  home_airport: { width: '6.5rem', render: (user) => user.home_airport },
};

/**
 * The report's default columns, which the table shows while the registry loads or if it
 * cannot be read, so the table and the downloads still agree.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'role', label: 'Role', default: true },
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'phone', label: 'Phone', default: true },
  { key: 'dart', label: 'DART', default: true },
  { key: 'kind', label: 'Kind', default: true },
  { key: 'membership', label: 'Membership', default: true },
];

/** `/admin/users` page: search accounts and see what each one may do. */
export function UsersListPage(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  // The order and the page live in the address beside the filters.
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage, sort, setSort: handleSortChange } = position;
  const role = filters.role ?? '';
  const kind = filters.kind ?? '';

  const query = useAdminUsers({
    search: filters.search ?? '',
    role: role as RoleSlug | '',
    is_active: activeParam(filters.is_active ?? ''),
    kind: kind as AccountKind | '',
    email_bounced: (filters.email_bounced ?? '') as 'true' | 'false' | '',
    ordering,
    page,
  });
  useFirstPageWhenMissing(position, query.error);

  const rows = query.data?.results ?? [];
  const count = query.data?.count ?? 0;

  const choice = useColumnChoice('roles', FALLBACK_COLUMNS);
  const columns = useMemo(
    () => reportTableColumns(choice.tableColumns, choice.tableChosen, CELLS, true),
    [choice.tableColumns, choice.tableChosen],
  );
  const disabledReason = exportDisabledReason(role, kind);
  const exportParams = {
    search: filters.search ?? '',
    role,
    kind,
    email_bounced: filters.email_bounced ?? '',
    columns: choice.chosen,
  };

  const handleReset = (): void => {
    setFilters(clearedValues(FILTER_FIELDS, filters));
  };

  return (
    <Page
      title="Users and roles"
      lede="Search accounts, grant, or remove roles, and send a password reset."
    >
      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(user) => user.id}
        caption={query.isSuccess ? `${count} account${count === 1 ? '' : 's'}` : undefined}
        label="Accounts"
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            label="Filter accounts"
          />
        }
        tools={<ColumnTools choice={choice} disabledReason={disabledReason} />}
        exportCsvUrl={reportExportUrl('roles', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('roles', 'pdf', exportParams)}
        exportDisabledReason={disabledReason}
        isLoading={query.isPending}
        onSortChange={handleSortChange}
        sort={sort}
        emptyTitle="No accounts match those filters"
        emptyDescription="Try a shorter search, or reset the filters."
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
          label: 'Account pages',
        }}
      />
    </Page>
  );
}
