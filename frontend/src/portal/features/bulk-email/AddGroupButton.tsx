/**
 * **Add a saved group**, beside **Add to batch**: puts everybody in a saved recipient
 * group into the batch at once.
 *
 * The button opens the same panel as **Start from a template**: a drop-down of the
 * groups, each with how many people it holds now, and **Add this group**, which adds
 * them as any add does: nobody already in the batch is added
 * twice, and the batch table names the group that brought each person in. Groups are
 * CalDART management's, so nobody else sees the button.
 */
import { useId, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailAddResult } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { PanelButton } from '@/portal/components/PanelButton';
import { hasAnyRole } from '@/portal/nav';
import { groupKindLabel } from './GroupKindChoice';
import './reuse.css';
import { useAddGroupToBatch, useGroups } from './reuseApi';
import { people } from './status';

interface AddGroupButtonProps {
  emailId: number;
  /** Told what the add did, for the card's status line. */
  onAdded: (result: BulkEmailAddResult) => void;
}

/** The button and its list of groups; nothing for a sender who is not management. */
export function AddGroupButton({ emailId, onAdded }: AddGroupButtonProps): JSX.Element | null {
  const { roles } = useAuth();
  if (!hasAnyRole(roles, ['management'])) return null;
  return (
    <PanelButton label="Add a saved group" legend="Add a saved group" isForm>
      {(handleClose) => (
        <GroupList
          emailId={emailId}
          onAdded={(result) => {
            handleClose();
            onAdded(result);
          }}
        />
      )}
    </PanelButton>
  );
}

/** The drop-down of groups, and **Add this group**, which adds the chosen one's people. */
function GroupList({ emailId, onAdded }: AddGroupButtonProps): JSX.Element {
  const groups = useGroups();
  const add = useAddGroupToBatch(emailId);
  const [chosen, setChosen] = useState('');
  const id = useId();

  if (groups.isPending) return <p role="status">Loading the groups…</p>;
  if (groups.isError) {
    return (
      <p className="field__error" role="alert">
        The groups didn&apos;t load. Try again in a moment.
      </p>
    );
  }
  if (groups.data.length === 0) {
    return (
      <p className="muted">
        No groups are saved yet. Build a recipient list, then press Save as a group under it.
      </p>
    );
  }
  return (
    <div className="stack-tight">
      <div className="field">
        <label className="field__label" htmlFor={id}>
          Group
        </label>
        <select id={id} value={chosen} onChange={(change) => setChosen(change.target.value)}>
          <option value="">Choose a group</option>
          {groups.data.map((group) => (
            <option key={group.id} value={String(group.id)}>
              {`${group.name}: ${groupKindLabel(group.kind).toLowerCase()}, ${
                group.count === null ? 'filters need fixing' : people(group.count)
              }`}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Button
          small
          disabled={chosen === '' || add.isPending}
          onClick={() => add.mutate(Number(chosen), { onSuccess: (result) => onAdded(result) })}
        >
          Add this group
        </Button>
      </div>
      {add.error === null ? null : (
        <p className="field__error" role="alert">
          {add.error instanceof ApiError
            ? add.error.message
            : "The group wasn't added. Try again in a moment."}
        </p>
      )}
    </div>
  );
}
