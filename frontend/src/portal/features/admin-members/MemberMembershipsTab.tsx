/**
 * The Memberships tab: the term history, an inline end-date/status correction,
 * and the "grant a term" form.
 *
 * Granting goes through the server's `activate_term`, so leaving the start date
 * blank does the right thing: a current member's new term begins the day after
 * their present one ends, and a lapsed member's begins today.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { usePlans } from '@/portal/api/queries';
import type { MemberDetail, MemberTerm, MembershipTermStatus } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { TERM_STATUS_CHOICES } from './choices';
import { useGrantTerm, useUpdateTerm } from './api';
import { splitErrors } from './errors';

interface TermEdit {
  ends_on: string;
  status: string;
  note: string;
}

function editFrom(term: MemberTerm): TermEdit {
  return { ends_on: term.ends_on ?? '', status: term.status, note: term.note };
}

/** The Memberships tab: term history, an inline correction form, and granting a term. */
export function MemberMembershipsTab({ member }: { member: MemberDetail }): JSX.Element {
  const toast = useToast();
  const plans = usePlans();
  const grant = useGrantTerm(member.id);
  const updateTerm = useUpdateTerm();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [edit, setEdit] = useState<TermEdit>({ ends_on: '', status: 'active', note: '' });

  const [plan, setPlan] = useState('');
  const [startsOn, setStartsOn] = useState('');
  const [note, setNote] = useState('');

  const grantErrors = splitErrors(grant.error);
  const termErrors = splitErrors(updateTerm.error);

  const startEditing = (term: MemberTerm) => {
    setEditingId(term.id);
    setEdit(editFrom(term));
  };

  const saveTerm = (term: MemberTerm) => {
    updateTerm.mutate(
      {
        termId: term.id,
        ends_on: edit.ends_on || null,
        status: edit.status as MembershipTermStatus,
        note: edit.note,
      },
      {
        onSuccess: () => {
          setEditingId(null);
          toast.show('Term updated.', 'success');
        },
      },
    );
  };

  const handleSubmitGrant = (event: React.FormEvent) => {
    event.preventDefault();
    grant.mutate(
      { plan, starts_on: startsOn || null, note },
      {
        onSuccess: (term) => {
          setPlan('');
          setStartsOn('');
          setNote('');
          toast.show(
            term.ends_on ? `Term granted through ${term.ends_on}.` : 'Lifetime membership granted.',
            'success',
          );
        },
      },
    );
  };

  const columns: Column<MemberTerm>[] = [
    { key: 'plan', header: 'Plan', render: (term) => term.plan },
    { key: 'starts_on', header: 'Starts', render: (term) => <DateText value={term.starts_on} /> },
    {
      key: 'ends_on',
      header: 'Ends',
      render: (term) =>
        editingId === term.id ? (
          <input
            type="date"
            aria-label="End date"
            value={edit.ends_on}
            onChange={(event) => setEdit({ ...edit, ends_on: event.target.value })}
          />
        ) : (
          <DateText value={term.ends_on} placeholder="Lifetime" />
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (term) =>
        editingId === term.id ? (
          <select
            aria-label="Term status"
            value={edit.status}
            onChange={(event) => setEdit({ ...edit, status: event.target.value })}
          >
            {TERM_STATUS_CHOICES.map((choice) => (
              <option key={choice.value} value={choice.value}>
                {choice.label}
              </option>
            ))}
          </select>
        ) : (
          term.status
        ),
    },
    { key: 'source', header: 'Source', render: (term) => term.source },
    {
      key: 'note',
      header: 'Note',
      render: (term) =>
        editingId === term.id ? (
          <input
            type="text"
            aria-label="Term note"
            value={edit.note}
            onChange={(event) => setEdit({ ...edit, note: event.target.value })}
          />
        ) : (
          <>
            {term.note}
            {term.granted_by ? <small className="muted"> (by {term.granted_by})</small> : null}
          </>
        ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (term) =>
        editingId === term.id ? (
          <span className="cluster">
            <Button small onClick={() => saveTerm(term)} disabled={updateTerm.isPending}>
              Save
            </Button>
            <Button small variant="quiet" onClick={() => setEditingId(null)}>
              Cancel
            </Button>
          </span>
        ) : (
          <Button small variant="quiet" onClick={() => startEditing(term)}>
            Edit
          </Button>
        ),
    },
  ];

  return (
    <>
      <Card title="Membership history" eyebrow="Terms">
        {termErrors.detail || termErrors.account.ends_on ? (
          <p role="alert" className="field__error">
            {termErrors.account.ends_on ?? termErrors.detail}
          </p>
        ) : null}
        <DataTable
          columns={columns}
          rows={member.memberships}
          rowKey={(term) => term.id}
          emptyTitle="No membership terms yet"
          emptyDescription="Grant one below, or wait for the member to pay online."
        />
      </Card>

      <Card title="Grant a term" eyebrow="Manual grant">
        <form onSubmit={handleSubmitGrant} noValidate>
          {grantErrors.detail ? (
            <p role="alert" className="field__error">
              {grantErrors.detail}
            </p>
          ) : null}
          <div className="grid">
            <div className="col-half">
              <Field label="Plan" required error={grantErrors.account.plan}>
                {(props) => (
                  <select
                    {...props}
                    required
                    value={plan}
                    onChange={(event) => setPlan(event.target.value)}
                  >
                    <option value="">Choose a plan</option>
                    {(plans.data ?? []).map((option) => (
                      <option key={option.slug} value={option.slug}>
                        {option.name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            </div>
            <div className="col-half">
              <Field
                label="Start date"
                hint="Leave blank to follow on from the current term."
                error={grantErrors.account.starts_on}
              >
                {(props) => (
                  <input
                    {...props}
                    type="date"
                    value={startsOn}
                    onChange={(event) => setStartsOn(event.target.value)}
                  />
                )}
              </Field>
            </div>
          </div>
          <Field label="Note" error={grantErrors.account.note}>
            {(props) => (
              <input
                {...props}
                type="text"
                placeholder="Why this term was granted"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            )}
          </Field>
          <Button type="submit" disabled={!plan || grant.isPending}>
            {grant.isPending ? 'Granting…' : 'Grant term'}
          </Button>
        </form>
      </Card>
    </>
  );
}
