/**
 * `/bulk-email/groups`: the people CalDART management mails again and again, saved
 * as groups and shared by every manager.
 *
 * One line per group: its name, which opens the group's page, where it is edited;
 * then **Download list** of its people (for a group that holds somebody) and a
 * trashcan that asks first, so both stay in sight on a phone; then whether it is
 * fixed or live, how many people it holds now, and when it last changed. **New group**
 * makes an empty one; the focus moves into its form, Escape closes it, and closing it
 * puts the focus back on **New group**. The usual way to make a group is **Save as a
 * group** under a batch on the compose screen.
 */
import { useCallback, useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import type { RecipientGroup, RecipientGroupKind } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import './bulk-email.css';
import './reuse.css';
import { GroupKindChoice, groupKindLabel } from './GroupKindChoice';
import { groupCsvUrl, useCreateGroup, useDeleteGroup, useGroups } from './reuseApi';
import { useFormCard } from './useFormCard';

/** What a live group's row says when the member list refuses one of its stored filters. */
export const FILTERS_NEED_FIXING = "This group's filters need fixing";

/** A line for the screen's status: what happened, and whether it went wrong. */
interface Notice {
  text: string;
  isError: boolean;
}

/** The groups table, its row controls, and the new group form. */
export function GroupsPage(): JSX.Element {
  const [isAdding, setIsAdding] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const newRef = useRef<HTMLButtonElement>(null);
  const handleClose = useCallback(() => setIsAdding(false), []);
  const formRef = useFormCard(isAdding ? 'new' : null, handleClose, newRef);
  const groups = useGroups();
  const remove = useDeleteGroup();
  const rows = groups.data ?? [];

  const handleDelete = (group: RecipientGroup): Promise<void> =>
    remove.mutateAsync(group.id).then(
      () => setNotice({ text: `${group.name} deleted.`, isError: false }),
      (error: unknown) =>
        setNotice({
          text: error instanceof Error ? error.message : `${group.name} was not deleted.`,
          isError: true,
        }),
    );

  const columns: Column<RecipientGroup>[] = [
    {
      key: 'name',
      header: 'Name',
      minWidth: '12rem',
      render: (group) => (
        <span className="cluster cluster--nowrap">
          <Link to={`/bulk-email/groups/${group.id}`}>{group.name}</Link>
          {group.needs_fixing ? (
            <Link className="field__error" to={`/bulk-email/groups/${group.id}`}>
              {FILTERS_NEED_FIXING}
            </Link>
          ) : null}
        </span>
      ),
      sortValue: (group) => group.name.toLowerCase(),
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '10.5rem',
      render: (group) => (
        <span className="cluster cluster--nowrap">
          {hasPeople(group) ? (
            <a
              className="button button--quiet button--small"
              href={groupCsvUrl(group.id)}
              aria-label={`Download the list of ${group.name}`}
              download
            >
              Download list
            </a>
          ) : null}
          <DeleteButton
            label={`Delete ${group.name}`}
            disabled={remove.isPending}
            onDelete={() => handleDelete(group)}
          />
        </span>
      ),
    },
    {
      key: 'kind',
      header: 'Kind',
      width: '5rem',
      render: (group) => groupKindLabel(group.kind),
      sortValue: (group) => group.kind,
    },
    {
      key: 'count',
      header: 'People',
      numeric: true,
      width: '5rem',
      render: (group) => group.count ?? 'Unknown',
      sortValue: (group) => group.count ?? -1,
    },
    {
      key: 'updated_at',
      header: 'Last edited',
      width: '7rem',
      render: (group) => <DateText value={group.updated_at} />,
      sortValue: (group) => group.updated_at,
    },
  ];

  return (
    <Page
      title="Recipient groups"
      eyebrow="Bulk Email"
      lede="People you email again and again, such as the board. Add a group to a batch on the compose screen with Add a saved group."
      actions={
        isAdding ? null : (
          <Button
            ref={newRef}
            onClick={() => {
              setNotice(null);
              setIsAdding(true);
            }}
          >
            New group
          </Button>
        )
      }
    >
      <Card>
        <dl className="bulk-email__kinds">
          <dt>Fixed</dt>
          <dd>The same people every time, until you add or remove someone.</dd>
          <dt>Live</dt>
          <dd>
            Filters, such as all friends in Marin. Each time the group is used it finds whoever
            matches them then.
          </dd>
        </dl>
      </Card>

      <div ref={formRef} className="bulk-email__form-slot">
        {isAdding ? <NewGroupCard onClose={handleClose} /> : null}
      </div>

      {notice === null ? null : (
        <p
          role={notice.isError ? 'alert' : 'status'}
          className={notice.isError ? 'field__error' : ''}
        >
          {notice.text}
        </p>
      )}

      <Card>
        {groups.isError ? (
          <p className="field__error" role="alert">
            The recipient groups could not be loaded.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={columns}
            rows={rows}
            rowKey={(group) => group.id}
            caption={`${rows.length} ${rows.length === 1 ? 'group' : 'groups'}`}
            emptyTitle="No recipient groups yet"
            emptyDescription="Press New group, or save a batch with Save as a group on the compose screen."
            isLoading={groups.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}

/** Whether `group` holds anybody now, so that its list is worth downloading. */
export function hasPeople(group: Pick<RecipientGroup, 'count'>): boolean {
  return group.count !== null && group.count > 0;
}

/** The new group form: a name and a kind, then the group's own page opens. */
function NewGroupCard({ onClose: handleClose }: { onClose: () => void }): JSX.Element {
  const [name, setName] = useState('');
  const [kind, setKind] = useState<RecipientGroupKind>('fixed');
  const create = useCreateGroup();
  const navigate = useNavigate();

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    create.mutate(
      { name, kind },
      { onSuccess: (group) => void navigate(`/bulk-email/groups/${group.id}`) },
    );
  };

  return (
    <Card eyebrow="New" title="New group">
      <form className="stack" aria-label="New group" onSubmit={handleSubmit}>
        <Field label="Name" error={fieldError(create.error, 'name')} required>
          {(props) => (
            <input
              {...props}
              maxLength={80}
              value={name}
              onChange={(change) => setName(change.target.value)}
            />
          )}
        </Field>
        <GroupKindChoice value={kind} onChange={(next) => setKind(next)} />
        <FormAlert error={create.error} handled={['name', 'kind']} />
        <div className="cluster">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? 'Saving…' : 'Make the group'}
          </Button>
          <Button variant="quiet" onClick={handleClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
