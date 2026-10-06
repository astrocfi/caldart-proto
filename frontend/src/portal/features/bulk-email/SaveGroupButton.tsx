/**
 * **Save as a group**, beside **Add these people**: keeps the search the filters make
 * as a saved recipient group, to add to an email's recipient list later with **Add a
 * saved group**. The recipient list plays no part.
 *
 * It asks for a name and the kind: fixed keeps the people the filters match now, live
 * keeps the filters, run again each time the group is used. The popup closes on
 * **Cancel**, Escape, or a click outside it. Groups are CalDART management's, so nobody
 * else sees the button.
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
import type { FilterValues } from '@/portal/reports/types';
import { givenFilters } from './api';
import { GroupKindChoice } from './GroupKindChoice';
import { useSaveGroup } from './reuseApi';

interface SaveGroupButtonProps {
  emailId: number;
  /** The filter bar's values: the search the group keeps. */
  filters: FilterValues;
}

/** The button, its form, and a line linking the saved group; nothing for non-management. */
export function SaveGroupButton({ emailId, filters }: SaveGroupButtonProps): JSX.Element | null {
  const { roles } = useAuth();
  const [saved, setSaved] = useState<RecipientGroup | null>(null);
  if (!hasAnyRole(roles, ['management'])) return null;
  return (
    <div className="stack-tight">
      <PanelButton label="Save as a group" legend="Save this search as a group" isForm>
        {(handleClose) => (
          <SaveGroupForm
            emailId={emailId}
            filters={filters}
            onCancel={handleClose}
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
  filters: FilterValues;
  onCancel: () => void;
  onSaved: (group: RecipientGroup) => void;
}

/** The group's name and kind, **Add group**, and **Cancel**. */
function SaveGroupForm({
  emailId,
  filters,
  onCancel: handleCancel,
  onSaved,
}: SaveGroupFormProps): JSX.Element {
  const [name, setName] = useState('');
  const [kind, setKind] = useState<RecipientGroupKind>('fixed');
  const save = useSaveGroup(emailId);

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    save.mutate(
      { name, kind, filters: givenFilters(filters) },
      { onSuccess: (group) => onSaved(group) },
    );
  };

  return (
    <form className="stack-tight" aria-label="Save this search as a group" onSubmit={handleSubmit}>
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
          {save.isPending ? 'Adding…' : 'Add group'}
        </Button>
        <Button variant="quiet" small onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
