/**
 * `/admin/users` — find an account and see what it may do.
 *
 * The list opens on active accounts, since a deactivated one is rarely what
 * anybody is looking for.  Its two export links download the CalDART roles
 * report, which has a section for every role but member and lists active
 * accounts only: the links carry the screen's search, role, and kind, never its
 * account status.  The report cannot follow two of the screen's choices, Donor
 * under Kind of account (a donor holds no role) and the Member role (the report
 * has no section for it), so while either is chosen the exports and the column
 * chooser are disabled and say why.  Nor does the report follow the **Email** filter,
 * which keeps the accounts whose address bounced: the exports carry it no more than
 * the account status.
 */
import { useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { AccountKind, RoleSlug, User } from '@/portal/api/types';
import { useRoles } from '@/portal/auth/useAuth';
import { ACCOUNT_KIND_LABELS, roleLabel } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { Field } from '@/portal/components/Field';
import { MembershipChip, StatusChip } from '@/portal/components/StatusChip';
import { Page } from '@/portal/components/Page';
import { useDebounced } from '@/portal/components/useDebounced';
import { reportExportUrl, useReportColumns } from '@/portal/reports/api';
import { useAdminUsers } from './api';

const PAGE_SIZE = 25;

type AccountStatus = 'true' | 'false' | '';

/** Whether the list keeps bounced addresses, the others, or both. */
type BounceFilter = 'true' | 'false' | '';

/** The status the list opens on: active accounts only. */
const INITIAL_STATUS: AccountStatus = 'true';

const DONOR_EXPORT_REASON = 'A donor holds no role, so the roles report lists nobody.';
const MEMBER_EXPORT_REASON = 'The roles report has no section for Member, so it lists nobody.';

/**
 * Why the roles report cannot follow the screen's filters, or `undefined` when it can.
 */
function exportDisabledReason(role: RoleSlug | '', kind: AccountKind | ''): string | undefined {
  if (kind === 'donor') return DONOR_EXPORT_REASON;
  if (role === 'member') return MEMBER_EXPORT_REASON;
  return undefined;
}

function displayName(user: User): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

const columns: Column<User>[] = [
  {
    key: 'last_name',
    header: 'Name',
    render: (user) => <Link to={`/admin/users/${user.id}`}>{displayName(user)}</Link>,
  },
  {
    key: 'email',
    header: 'Email',
    render: (user) => <span className="mono">{user.email}</span>,
  },
  {
    key: 'roles',
    header: 'Roles',
    render: (user) =>
      user.roles.length > 0 ? (
        <span className="cluster">
          {user.roles.map((role) => (
            <span key={role} className="chip chip--neutral">
              {roleLabel(role)}
            </span>
          ))}
        </span>
      ) : (
        <span className="muted">—</span>
      ),
  },
  {
    key: 'kind',
    header: 'Kind',
    render: (user) => ACCOUNT_KIND_LABELS[user.kind],
  },
  {
    key: 'membership',
    header: 'Membership',
    render: (user) => <MembershipChip membership={user.membership} />,
  },
  {
    key: 'is_active',
    header: 'Account',
    render: (user) =>
      user.is_active ? (
        <StatusChip tone="current" label="Active" />
      ) : (
        <StatusChip tone="expired" label="Deactivated" />
      ),
  },
];

/** `/admin/users` page: search accounts and see what each one may do. */
export function UsersListPage(): JSX.Element {
  const [search, setSearch] = useState('');
  const [role, setRole] = useState<RoleSlug | ''>('');
  const [isActive, setIsActive] = useState<AccountStatus>(INITIAL_STATUS);
  const [kind, setKind] = useState<AccountKind | ''>('');
  const [bounced, setBounced] = useState<BounceFilter>('');
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search);
  const roles = useRoles();
  const query = useAdminUsers({
    search: debouncedSearch,
    role,
    is_active: isActive,
    kind,
    email_bounced: bounced,
    page,
  });

  // Any change to the filters puts us back on the first page.
  useEffect(() => setPage(1), [debouncedSearch, role, isActive, kind, bounced]);

  const rows = query.data?.results ?? [];
  const count = query.data?.count ?? 0;
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE));

  const registry = useReportColumns('roles');
  const reportColumns = useMemo(() => registry.data ?? [], [registry.data]);
  // Null means "whatever the registry calls default": the chooser has not been
  // touched, so it must follow a registry that is still loading.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const chosenKeys = chosen ?? defaultColumnKeys(reportColumns);
  const disabledReason = exportDisabledReason(role, kind);
  const exportParams = { search: debouncedSearch, role, kind, columns: chosenKeys };

  const handleColumnChange = (next: string[]) => {
    setChosen(next);
  };

  const columnChooser = registry.isError ? (
    <p className="muted">
      The columns could not be loaded; the downloads carry the default columns.
    </p>
  ) : reportColumns.length === 0 ? null : disabledReason !== undefined ? (
    <Button variant="quiet" small disabled title={disabledReason}>
      Columns
    </Button>
  ) : (
    <ColumnChooser
      report="roles"
      columns={reportColumns}
      chosen={chosenKeys}
      onChange={handleColumnChange}
      legend="Columns to export"
    />
  );

  const filters = (
    <>
      <Field label="Search">
        {(props) => (
          <input
            {...props}
            type="search"
            name="search"
            placeholder="Name or email"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        )}
      </Field>
      <Field label="Kind of account">
        {(props) => (
          <select
            {...props}
            name="kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as AccountKind | '')}
          >
            <option value="">Every kind</option>
            {(Object.keys(ACCOUNT_KIND_LABELS) as AccountKind[]).map((value) => (
              <option key={value} value={value}>
                {ACCOUNT_KIND_LABELS[value]}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Account status">
        {(props) => (
          <select
            {...props}
            name="is_active"
            value={isActive}
            onChange={(event) => setIsActive(event.target.value as AccountStatus)}
          >
            <option value="">Active and deactivated</option>
            <option value="true">Active only</option>
            <option value="false">Deactivated only</option>
          </select>
        )}
      </Field>
      <Field label="Email">
        {(props) => (
          <select
            {...props}
            name="email_bounced"
            value={bounced}
            onChange={(event) => setBounced(event.target.value as BounceFilter)}
          >
            <option value="">Any address</option>
            <option value="true">Email bounced</option>
            <option value="false">Not bounced</option>
          </select>
        )}
      </Field>
      {columnChooser}
    </>
  );

  return (
    <Page
      title="Users and roles"
      eyebrow="Administration"
      lede="Search accounts, grant, or remove roles, and send a password reset."
    >
      <fieldset>
        <legend>Filter by role</legend>
        <div className="cluster">
          <Button
            variant={role === '' ? 'secondary' : 'quiet'}
            small
            aria-pressed={role === ''}
            onClick={() => setRole('')}
          >
            Any role
          </Button>
          {(roles.data ?? []).map((entry) => (
            <Button
              key={entry.slug}
              variant={role === entry.slug ? 'secondary' : 'quiet'}
              small
              aria-pressed={role === entry.slug}
              title={entry.description}
              onClick={() => setRole(role === entry.slug ? '' : entry.slug)}
            >
              {roleLabel(entry.slug)}
            </Button>
          ))}
        </div>
      </fieldset>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(user) => user.id}
        caption={
          query.isSuccess
            ? `${count} account${count === 1 ? '' : 's'}${count > PAGE_SIZE ? ` · page ${page} of ${lastPage}` : ''}`
            : undefined
        }
        filters={filters}
        exportCsvUrl={reportExportUrl('roles', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('roles', 'pdf', exportParams)}
        exportDisabledReason={disabledReason}
        isLoading={query.isPending}
        emptyTitle="No accounts match those filters"
        emptyDescription="Try a shorter search, or clear the role filter."
      />

      {lastPage > 1 ? (
        <nav className="cluster" aria-label="Pagination">
          <Button
            variant="quiet"
            small
            disabled={!query.data?.previous}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </Button>
          <span className="muted">
            Page {page} of {lastPage}
          </span>
          <Button
            variant="quiet"
            small
            disabled={!query.data?.next}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </Button>
        </nav>
      ) : null}
    </Page>
  );
}
