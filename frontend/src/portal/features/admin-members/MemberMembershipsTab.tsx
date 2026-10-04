/**
 * The Memberships tab: the term history, an inline end-date/status correction,
 * and the "grant a term" form.
 *
 * Granting goes through the server's `activate_term`, so leaving the start date
 * blank does the right thing: a current member's new term begins the day after
 * their present one ends, and a lapsed member's begins today.  A donor, a "Deleted
 * member N" record included, is offered no grant: the server refuses one.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, KeyboardEvent } from 'react';

import { usePlans } from '@/portal/api/queries';
import type { MemberDetail, MemberTerm, MembershipTermStatus } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText, formatDate } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { RefusedSubmitNote, useRefusedSubmit } from '@/portal/components/RefusedSubmit';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { TERM_SOURCE_LABELS, TERM_STATUS_CHOICES } from './choices';
import { useGrantTerm, useUpdateTerm } from './api';
import { splitErrors } from './errors';

/** Why a donor's history is empty and offers no grant. */
const DONOR_NO_TERMS = 'A donor holds no membership, and becomes a member only by registering.';

interface TermEdit {
  ends_on: string;
  status: string;
  note: string;
}

/** The dot beside a term's state: green active, red expired, gray canceled or suspended. */
const TERM_STATUS_TONE: Record<MembershipTermStatus, StatusTone> = {
  active: 'current',
  expired: 'expired',
  canceled: 'none',
  suspended: 'none',
};

/** A term's state in words, as the correction form's choices word it. */
function termStatusLabel(status: MembershipTermStatus): string {
  return TERM_STATUS_CHOICES.find((choice) => choice.value === status)?.label ?? status;
}

function editFrom(term: MemberTerm): TermEdit {
  return { ends_on: term.ends_on ?? '', status: term.status, note: term.note };
}

/** The Memberships tab: term history, an inline correction form, and granting a term. */
export function MemberMembershipsTab({ member }: { member: MemberDetail }): JSX.Element {
  const isDonor = member.kind === 'donor';
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
  const grantRef = useRef<HTMLFormElement>(null);
  const grantRefusal = useRefusedSubmit(grantRef, grant.error);

  // The focus follows a term edit: into its end date as it opens, and back to the
  // row's Edit as it closes; a granted term's Edit takes it too, once the row shows.
  const editButtons = useRef(new Map<number, HTMLButtonElement | null>());
  const endDateRef = useRef<HTMLInputElement>(null);
  const [focusTermId, setFocusTermId] = useState<number | null>(null);

  useEffect(() => {
    if (editingId !== null) endDateRef.current?.focus();
  }, [editingId]);

  useEffect(() => {
    if (focusTermId === null) return;
    const button = editButtons.current.get(focusTermId);
    if (button === null || button === undefined) return;
    setFocusTermId(null);
    button.focus();
  }, [focusTermId, member.memberships]);

  const startEditing = (term: MemberTerm) => {
    setEditingId(term.id);
    setEdit(editFrom(term));
  };

  const handleStopEditing = (): void => {
    setFocusTermId(editingId);
    setEditingId(null);
  };

  // Escape in the row being edited is Cancel.
  const handleEditKeyDown = (event: KeyboardEvent<HTMLElement>): void => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    handleStopEditing();
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
          handleStopEditing();
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
          setFocusTermId(term.id);
          setPlan('');
          setStartsOn('');
          setNote('');
          toast.show(
            term.ends_on
              ? `Term granted through ${formatDate(term.ends_on)}.`
              : 'Lifetime membership granted.',
            'success',
          );
        },
      },
    );
  };

  const columns: Column<MemberTerm>[] = [
    {
      key: 'plan',
      header: 'Plan',
      isIdentity: true,
      minWidth: '8rem',
      render: (term) => term.plan,
    },
    {
      key: 'starts_on',
      header: 'Starts',
      width: '8rem',
      dropOrder: 2,
      render: (term) => <DateText value={term.starts_on} />,
    },
    {
      key: 'ends_on',
      header: 'Ends',
      width: '9.5rem',
      dropOrder: 4,
      render: (term) =>
        editingId === term.id ? (
          <input
            ref={endDateRef}
            type="date"
            aria-label="End date"
            onKeyDown={handleEditKeyDown}
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
      width: '8rem',
      keepInSight: true,
      narrowWidth: '6rem',
      render: (term) =>
        editingId === term.id ? (
          <select
            aria-label="Term status"
            onKeyDown={handleEditKeyDown}
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
          <StatusDot tone={TERM_STATUS_TONE[term.status]} label={termStatusLabel(term.status)} />
        ),
    },
    {
      key: 'source',
      header: 'Source',
      width: '8.5rem',
      dropOrder: 1,
      render: (term) => TERM_SOURCE_LABELS[term.source],
    },
    {
      key: 'note',
      header: 'Note',
      minWidth: '8rem',
      dropOrder: 3,
      render: (term) =>
        editingId === term.id ? (
          <input
            type="text"
            aria-label="Term note"
            onKeyDown={handleEditKeyDown}
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
      isActions: true,
      narrowWidth: '5rem',
      render: (term) =>
        editingId === term.id ? (
          <span className="cluster">
            <Button
              small
              onClick={() => saveTerm(term)}
              onKeyDown={handleEditKeyDown}
              disabled={updateTerm.isPending}
            >
              Save
            </Button>
            <Button small variant="quiet" onClick={handleStopEditing} onKeyDown={handleEditKeyDown}>
              Cancel
            </Button>
          </span>
        ) : (
          <Button
            ref={(node) => {
              editButtons.current.set(term.id, node);
            }}
            small
            variant="quiet"
            onClick={() => startEditing(term)}
          >
            Edit
          </Button>
        ),
    },
  ];

  return (
    <>
      <Card title="Membership history">
        {termErrors.detail || termErrors.account.ends_on ? (
          <p role="alert" className="field__error">
            {termErrors.account.ends_on ?? termErrors.detail}
          </p>
        ) : null}
        <DataTable
          singleLine
          columns={columns}
          rows={member.memberships}
          rowKey={(term) => term.id}
          emptyTitle="No membership terms yet"
          emptyDescription={
            isDonor ? DONOR_NO_TERMS : 'Grant one below, or wait for the member to pay online.'
          }
        />
      </Card>

      {isDonor ? null : (
        <Card title="Grant a term">
          <form ref={grantRef} onSubmit={handleSubmitGrant} noValidate>
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
            <div className="cluster">
              <Button type="submit" disabled={!plan || grant.isPending}>
                {grant.isPending ? 'Granting…' : 'Grant term'}
              </Button>
              <RefusedSubmitNote count={grantRefusal.count} />
            </div>
          </form>
        </Card>
      )}
    </>
  );
}
