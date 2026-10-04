/**
 * The form behind **Add an email type** and each row's **Edit** on `/bulk-email/types`.
 *
 * A type has a name, a sentence saying what it is for (which members read beside the
 * switch that turns it off), the roles that may send it, and whether recipients may
 * turn it off. The server checks the name against every other type.
 */
import { useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { EmailType, EmailTypeInput, EmailTypeSenderRole } from '@/portal/api/types';
import { roleLabel } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { FormAlert, fieldError } from '@/portal/features/auth/form';

/** The roles a type may name as its senders, in the order the server keeps them. */
export const SENDER_ROLES: readonly EmailTypeSenderRole[] = ['dart_leader', 'management'];

/** The fields the form shows the server's complaints beside. */
const HANDLED_FIELDS = ['name', 'description', 'sender_roles'];

export interface EmailTypeFormProps {
  /** The type to edit; without one the form adds a type. */
  emailType?: EmailType;
  /** Shown on the submit button. */
  submitLabel: string;
  pending: boolean;
  /** The last save's error, shown beside its field. */
  error: unknown;
  onSubmit: (input: EmailTypeInput) => void;
  onCancel: () => void;
}

/** The type's name, description, senders, and whether it may be turned off. */
export function EmailTypeForm({
  emailType,
  submitLabel,
  pending,
  error,
  onSubmit: handleSave,
  onCancel: handleCancel,
}: EmailTypeFormProps): JSX.Element {
  const [name, setName] = useState(emailType?.name ?? '');
  const [description, setDescription] = useState(emailType?.description ?? '');
  const [senders, setSenders] = useState<Set<EmailTypeSenderRole>>(
    () => new Set(emailType?.sender_roles ?? []),
  );
  const [allowOptOut, setAllowOptOut] = useState(emailType?.allow_opt_out ?? true);
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, error);
  // The server's complaint about a field goes once the field is edited.
  const shown = useFreshErrors(
    error,
    { name, description, sender_roles: senders },
    {
      name: fieldError(error, 'name'),
      description: fieldError(error, 'description'),
      sender_roles: fieldError(error, 'sender_roles'),
    },
  );

  const handleSenderChange = (role: EmailTypeSenderRole, isChecked: boolean): void => {
    setSenders((current) => {
      const next = new Set(current);
      if (isChecked) next.add(role);
      else next.delete(role);
      return next;
    });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    handleSave({
      name,
      description,
      allow_opt_out: allowOptOut,
      sender_roles: SENDER_ROLES.filter((role) => senders.has(role)),
    });
  };

  const sendersError = shown.sender_roles ?? null;

  return (
    <form ref={formRef} className="stack" aria-label={submitLabel} onSubmit={handleSubmit}>
      <Field label="Name" error={shown.name} required>
        {(props) => (
          <input
            {...props}
            maxLength={60}
            value={name}
            onChange={(change) => setName(change.target.value)}
          />
        )}
      </Field>
      <Field
        label="What it is for"
        hint="One sentence. Members read it beside the switch that turns this email off."
        error={shown.description}
        required
      >
        {(props) => (
          <textarea
            {...props}
            rows={2}
            value={description}
            onChange={(change) => setDescription(change.target.value)}
          />
        )}
      </Field>

      <fieldset className="stack">
        <legend>Who may send it</legend>
        <p className="muted">A system administrator can send every type.</p>
        {SENDER_ROLES.map((role) => (
          <label key={role} className="cluster">
            <input
              type="checkbox"
              checked={senders.has(role)}
              onChange={(change) => handleSenderChange(role, change.target.checked)}
            />
            {roleLabel(role)}
          </label>
        ))}
        {sendersError === null ? null : (
          <p className="field__error" role="alert">
            {sendersError}
          </p>
        )}
      </fieldset>

      <div className="field">
        <label className="cluster">
          <input
            type="checkbox"
            checked={allowOptOut}
            onChange={(change) => setAllowOptOut(change.target.checked)}
          />
          Recipients may turn it off
        </label>
        <span className="field__hint">
          Each email then carries an unsubscribe link. Leave this off only for email every member
          must receive; turning it back on restores everyone&apos;s earlier choice.
        </span>
      </div>

      <FormAlert error={error} handled={HANDLED_FIELDS} />

      <div className="cluster">
        <Button type="submit" disabled={pending}>
          {pending ? 'Saving…' : submitLabel}
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
        <RefusedSubmitNote count={refusal.count} />
      </div>
    </form>
  );
}
