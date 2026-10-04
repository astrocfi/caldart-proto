/**
 * **Add a saved group**, beside **Add to batch**: puts everybody in a saved recipient
 * group into the batch at once.
 *
 * The button opens a list of the groups, each with how many people it holds now;
 * choosing one adds them, as any add does: nobody already in the batch is added
 * twice, and the batch table names the group that brought each person in. Groups are
 * CalDART management's, so nobody else sees the button.
 */
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
    <PanelButton label="Add a saved group" legend="Choose a saved group to add">
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

/** One button per group, which adds its people. */
function GroupList({ emailId, onAdded }: AddGroupButtonProps): JSX.Element {
  const groups = useGroups();
  const add = useAddGroupToBatch(emailId);

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
      <ul className="bulk-email__choices">
        {groups.data.map((group) => (
          <li key={group.id}>
            <Button
              variant="quiet"
              small
              disabled={add.isPending}
              onClick={() => add.mutate(group.id, { onSuccess: (result) => onAdded(result) })}
            >
              {`${group.name}: ${groupKindLabel(group.kind).toLowerCase()}, ${
                group.count === null ? 'filters need fixing' : people(group.count)
              }`}
            </Button>
          </li>
        ))}
      </ul>
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
