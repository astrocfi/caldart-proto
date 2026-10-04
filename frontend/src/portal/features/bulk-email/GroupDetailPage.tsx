/**
 * `/bulk-email/groups/:id`: one saved recipient group.
 *
 * The name can be changed at the top. A fixed group lists its people, with a box
 * that finds a member or friend by name or address to add and a trashcan on each
 * row that asks first. A live group lists its filter sets, each with a trashcan,
 * and the member list's filter bar with **Add these filters**, which empties the bar
 * and says what it added; under them, everybody the filters find now. A filter set
 * the member list no longer accepts is marked, and the group's people wait until it
 * is taken out. Either kind downloads its people as a spreadsheet with **Download
 * list**, offered while the group holds anybody.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { GroupPerson, PersonMatch, RecipientGroup } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Field } from '@/portal/components/Field';
import { FilterBar } from '@/portal/components/FilterBar';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { Typeahead } from '@/portal/components/Typeahead';
import { fieldError } from '@/portal/features/auth/form';
import type { FilterValues } from '@/portal/reports/types';
import { givenFilters } from './api';
import { DROP_ORDER } from './dropOrder';
import './bulk-email.css';
import './reuse.css';
import { groupKindLabel } from './GroupKindChoice';
import { FILTER_FIELDS, useDartOptions } from './RecipientsCard';
import {
  groupCsvUrl,
  useAddGroupFilters,
  useAddGroupMember,
  useGroup,
  useGroupPeople,
  usePeopleMatching,
  useRemoveGroupFilters,
  useRemoveGroupMember,
  useRenameGroup,
} from './reuseApi';
import { kindLabel, people } from './status';

/** What a failed request says when the server gave no sentence of its own. */
const FALLBACK_ERROR = 'That did not work. Try again.';

/** What a filter set the member list no longer accepts says beside itself. */
export const NEEDS_FIXING_HINT =
  'The member list no longer accepts these filters, such as a DART that was deleted. Take them out and add the right ones.';

/** The group named in the address. */
export function GroupDetailPage(): JSX.Element {
  const id = Number(useParams().id);
  const group = useGroup(id);

  if (group.isError) {
    return (
      <Page title="Recipient group">
        <p className="field__error" role="alert">
          This group could not be loaded. It may have been deleted.{' '}
          <Link to="/bulk-email/groups">See every group</Link>.
        </p>
      </Page>
    );
  }
  if (group.data === undefined) return <Loading />;
  const current = group.data;

  return (
    <Page
      title={current.name}
      lede={
        current.kind === 'fixed'
          ? 'A fixed group: the same people every time, until you add or remove someone.'
          : 'A live group: each time it is used, it finds whoever matches its filters then.'
      }
    >
      <p>
        <Link to="/bulk-email/groups">All recipient groups</Link>
      </p>
      {/* Keyed by the name, so the box starts again from the name as saved. */}
      <RenameCard key={current.name} group={current} />
      {current.kind === 'live' ? <FiltersCard group={current} /> : null}
      <PeopleCard group={current} />
    </Page>
  );
}

/** The group's name, and **Save name**. */
function RenameCard({ group }: { group: RecipientGroup }): JSX.Element {
  const [name, setName] = useState(group.name);
  const rename = useRenameGroup(group.id);
  const toast = useToast();

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    rename.mutate(name, { onSuccess: (saved) => toast.show(`Renamed ${saved.name}.`, 'success') });
  };

  return (
    <Card title="Name">
      <form className="cluster" aria-label="Rename the group" onSubmit={handleSubmit}>
        <Field label="Group name" error={fieldError(rename.error, 'name')} required>
          {(props) => (
            <input
              {...props}
              maxLength={80}
              value={name}
              onChange={(change) => setName(change.target.value)}
            />
          )}
        </Field>
        <Button
          type="submit"
          variant="secondary"
          disabled={rename.isPending || name === group.name}
        >
          Save name
        </Button>
      </form>
    </Card>
  );
}

/** A live group's filter sets, each with a trashcan, and the bar that adds another. */
function FiltersCard({ group }: { group: RecipientGroup }): JSX.Element {
  const [filters, setFilters] = useState<FilterValues>({});
  // Moved on after each add, so the filter bar starts again empty.
  const [barKey, setBarKey] = useState(0);
  const [added, setAdded] = useState<string | null>(null);
  const add = useAddGroupFilters(group.id);
  const remove = useRemoveGroupFilters(group.id);
  const dartOptions = useDartOptions();
  const failure = add.error ?? remove.error;

  return (
    <Card title="Filters">
      <p className="muted">
        The group holds everybody any of these filters find. Choose more with the filter bar, then
        press <strong>Add these filters</strong>.
      </p>
      {group.filter_sets.length === 0 ? (
        <p>This group has no filters yet, so it holds nobody.</p>
      ) : (
        <ul className="bulk-email__choices">
          {group.filter_sets.map((filterSet) => (
            <li key={filterSet.id} className="cluster">
              <span>{filterSet.label}</span>
              {filterSet.needs_fixing ? (
                <span className="field__error">{NEEDS_FIXING_HINT}</span>
              ) : null}
              <DeleteButton
                label={`Remove the filters ${filterSet.label}`}
                confirmLabel="Remove"
                onDelete={() => remove.mutateAsync(filterSet.id)}
              />
            </li>
          ))}
        </ul>
      )}
      <FilterBar
        key={barKey}
        fields={FILTER_FIELDS}
        values={filters}
        onChange={(next) => setFilters(next)}
        options={dartOptions}
        label="Choose filters to add"
      />
      <div className="cluster">
        <Button
          disabled={add.isPending}
          onClick={() => {
            setAdded(null);
            add.mutate(givenFilters(filters), {
              onSuccess: (filterSet) => {
                setFilters({});
                setBarKey((count) => count + 1);
                setAdded(filterSet.label);
              },
            });
          }}
        >
          Add these filters
        </Button>
      </div>
      {added === null ? null : <p role="status">{`Added the filters ${added}.`}</p>}
      <p className="muted">With no filters chosen, this adds every member and friend.</p>
      {failure === null ? null : (
        <p className="field__error" role="alert">
          {failure instanceof ApiError ? failure.message : FALLBACK_ERROR}
        </p>
      )}
    </Card>
  );
}

/** Everybody in the group now; for a fixed group, the box that adds one more. */
function PeopleCard({ group }: { group: RecipientGroup }): JSX.Element {
  const members = useGroupPeople(group.id);
  const remove = useRemoveGroupMember(group.id);
  const isFixed = group.kind === 'fixed';
  const count = members.data?.count ?? group.count;
  const countText = count === null ? 'people the filters cannot find yet' : people(count);

  // The trashcan comes last and stays in sight; the DART, the kind, then the address
  // give way on a narrow screen.
  const columns: Column<GroupPerson>[] = [
    {
      key: 'name',
      header: 'Name',
      minWidth: '14rem',
      isIdentity: true,
      render: (person) => (person.is_active ? person.name : `${person.name} (deactivated)`),
      sortValue: (person) => person.name,
    },
    ...(isFixed
      ? [
          {
            key: 'remove',
            header: 'Remove',
            isActions: true,
            render: (person: GroupPerson) => (
              <DeleteButton
                label={`Remove ${person.name || person.email} from the group`}
                confirmLabel="Remove"
                onDelete={() => remove.mutateAsync(person.user_id)}
              />
            ),
          },
        ]
      : []),
    {
      key: 'email',
      header: 'Email',
      minWidth: '14rem',
      dropOrder: DROP_ORDER.address,
      render: (person) => person.email,
      sortValue: (person) => person.email,
    },
    {
      key: 'kind',
      header: 'Kind',
      width: '5.5rem',
      dropOrder: DROP_ORDER.kind,
      render: (person) => kindLabel(person.kind),
    },
    {
      key: 'dart',
      header: 'DART',
      width: '8rem',
      dropOrder: DROP_ORDER.dart,
      render: (person) => person.dart_name || '—',
    },
  ];

  return (
    <Card title={isFixed ? 'People' : 'Who it finds now'}>
      {isFixed ? <AddPerson groupId={group.id} /> : null}
      <p>
        <strong>{`${groupKindLabel(group.kind)} group of ${countText}.`}</strong>
      </p>
      {members.isError ? (
        <p className="field__error" role="alert">
          {members.error instanceof ApiError
            ? `${members.error.message} ${NEEDS_FIXING_HINT}`
            : 'The people could not be loaded.'}
        </p>
      ) : (
        <DataTable
          singleLine
          columns={columns}
          rows={members.data?.people ?? []}
          rowKey={(person) => person.user_id}
          caption={`${group.name}: ${countText}`}
          emptyTitle="Nobody is in this group"
          emptyDescription={
            isFixed ? 'Find somebody above to add them.' : 'Add filters above to find people.'
          }
          isLoading={members.isLoading}
        />
      )}
      {remove.error === null ? null : (
        <p className="field__error" role="alert">
          {remove.error instanceof ApiError ? remove.error.message : FALLBACK_ERROR}
        </p>
      )}
      {count === null || count === 0 ? null : (
        <div className="cluster">
          <a className="button button--quiet" href={groupCsvUrl(group.id)} download>
            Download list
          </a>
        </div>
      )}
    </Card>
  );
}

/** A box that finds a member or friend by name or address, and adds the one picked. */
function AddPerson({ groupId }: { groupId: number }): JSX.Element {
  const [text, setText] = useState('');
  const [added, setAdded] = useState<string | null>(null);
  const add = useAddGroupMember(groupId);

  const handlePick = (person: PersonMatch): void => {
    setAdded(null);
    add.mutate(person.id, {
      onSuccess: () => {
        setText('');
        setAdded(person.name);
      },
    });
  };

  return (
    <div className="stack-tight">
      <Field
        label="Add a person"
        error={fieldError(add.error, 'user') ?? (add.error === null ? null : add.error.message)}
        hint="Type part of a name or an email address, then choose the person."
      >
        {(props) => (
          <Typeahead
            {...props}
            listLabel="Matching people"
            value={text}
            onValueChange={(next) => setText(next)}
            onPick={handlePick}
            useSuggestions={usePeopleMatching}
            itemKey={(person) => String(person.id)}
            itemLabel={(person) => person.name}
            itemMeta={(person) => person.email}
          />
        )}
      </Field>
      {added === null ? null : <p role="status">{`${added} added.`}</p>}
    </div>
  );
}
