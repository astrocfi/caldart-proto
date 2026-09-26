/** `/admin/users` — find an account and see what it may do. */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { AccountKind, RoleSlug, User } from '@/portal/api/types';
import { useRoles } from '@/portal/auth/useAuth';
import { ACCOUNT_KIND_LABELS, roleLabel } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { Field } from '@/portal/components/Field';
import { MembershipChip, StatusChip } from '@/portal/components/StatusChip';
import { Page } from '@/portal/components/Page';
import { useDebounced } from '@/portal/components/useDebounced';
import { useAdminUsers } from './api';

const PAGE_SIZE = 25;

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
  const [isActive, setIsActive] = useState<'true' | 'false' | ''>('');
  const [kind, setKind] = useState<AccountKind | ''>('');
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search);
  const roles = useRoles();
  const query = useAdminUsers({ search: debouncedSearch, role, is_active: isActive, kind, page });

  // Any change to the filters puts us back on the first page.
  useEffect(() => setPage(1), [debouncedSearch, role, isActive, kind]);

  const rows = query.data?.results ?? [];
  const count = query.data?.count ?? 0;
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE));

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
      <Field label="Account status">
        {(props) => (
          <select
            {...props}
            name="is_active"
            value={isActive}
            onChange={(event) => setIsActive(event.target.value as 'true' | 'false' | '')}
          >
            <option value="">Active and deactivated</option>
            <option value="true">Active only</option>
            <option value="false">Deactivated only</option>
          </select>
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
