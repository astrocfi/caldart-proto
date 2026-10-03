/**
 * **Save as a group**, under the batch: keeps the batch as a saved recipient group,
 * to add to another email's batch later with **Add a saved group**.
 *
 * It asks for a name and the kind: fixed keeps these exact people, live keeps the
 * filters that chose them. Groups are CalDART management's, so nobody else sees the
 * button.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { Link } from 'react-router-dom';

import type { RecipientGroup, RecipientGroupKind } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { PanelButton } from '@/portal/components/PanelButton';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { hasAnyRole } from '@/portal/nav';
import { GroupKindChoice } from './GroupKindChoice';
import { useSaveGroup } from './reuseApi';

/** The button, its form, and a line linking the saved group; nothing for non-management. */
export function SaveGroupButton({ emailId }: { emailId: number }): JSX.Element | null {
  const { roles } = useAuth();
  const [saved, setSaved] = useState<RecipientGroup | null>(null);
  if (!hasAnyRole(roles, ['management'])) return null;
  return (
    <div className="stack-tight">
      <PanelButton label="Save as a group" legend="Save the batch as a group">
        {(handleClose) => (
          <SaveGroupForm
            emailId={emailId}
            onSaved={(group) => {
              handleClose();
              setSaved(group);
            }}
          />
        )}
      </PanelButton>
      {saved === null ? null : (
        <p role="status">
          Saved as the group <Link to={`/bulk-email/groups/${saved.id}`}>{saved.name}</Link>.
        </p>
      )}
    </div>
  );
}

interface SaveGroupFormProps {
  emailId: number;
  onSaved: (group: RecipientGroup) => void;
}

/** The group's name and kind, and **Save group**. */
function SaveGroupForm({ emailId, onSaved }: SaveGroupFormProps): JSX.Element {
  const [name, setName] = useState('');
  const [kind, setKind] = useState<RecipientGroupKind>('fixed');
  const save = useSaveGroup(emailId);

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    save.mutate({ name, kind }, { onSuccess: (group) => onSaved(group) });
  };

  return (
    <form className="stack-tight" aria-label="Save the batch as a group" onSubmit={handleSubmit}>
      <Field label="Group name" error={fieldError(save.error, 'name')} required>
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
      <FormAlert error={save.error} handled={['name', 'kind']} />
      <div className="cluster">
        <Button type="submit" small disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save group'}
        </Button>
      </div>
    </form>
  );
}
