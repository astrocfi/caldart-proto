/**
 * The member profile form.
 *
 * One component serves both `/profile` and step 2 of the join wizard.  The
 * fields themselves are `<ProfileFieldsets/>`, shared with the administrator's
 * member screens; what this adds is the state, the inline validation and the
 * submit button a member needs.
 */
import { useEffect, useState } from 'react';
import type { FormEvent, JSX, ReactNode } from 'react';

import type { ProfilePatch } from '../../api/types';
import { Button } from '../../components/Button';
import { useDarts } from './api';
import { ProfileFieldsets } from './ProfileFieldsets';
import { formToPatch, validateProfileForm } from './form';
import type { ProfileFormErrors, ProfileFormValues } from './form';
import './profile.css';

export interface ProfileFormProps {
  initialValues: ProfileFormValues;
  onSubmit: (patch: ProfilePatch, values: ProfileFormValues) => void;
  submitting?: boolean;
  submitLabel?: string;
  /** Field-keyed messages from a rejected save, merged with the inline ones. */
  serverErrors?: Record<string, string>;
  /** Rendered beside the submit button — a "Back" link in the wizard. */
  secondaryAction?: ReactNode;
}

/** The member profile form: validated fieldsets, a submit button, and an optional action. */
export function ProfileForm({
  initialValues,
  onSubmit,
  submitting = false,
  submitLabel = 'Save profile',
  serverErrors,
  secondaryAction,
}: ProfileFormProps): JSX.Element {
  const [values, setValues] = useState<ProfileFormValues>(initialValues);
  const [errors, setErrors] = useState<ProfileFormErrors>({});
  const [submitted, setSubmitted] = useState(false);
  const darts = useDarts();

  // Re-check as the member types, but only once they have tried to submit —
  // nobody wants to be told a field is empty before they reach it.
  useEffect(() => {
    if (submitted) setErrors(validateProfileForm(values));
  }, [submitted, values]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    const found = validateProfileForm(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    onSubmit(formToPatch(values), values);
  }

  /** Inline rules win; a server message fills in anything they missed. */
  const shownErrors: ProfileFormErrors = { ...serverErrors, ...errors };

  const hasErrors = Object.keys(errors).length > 0;

  return (
    <form onSubmit={handleSubmit} noValidate className="profile-form">
      <ProfileFieldsets
        value={values}
        onChange={setValues}
        errors={shownErrors}
        darts={darts.data ?? []}
        dartsLoading={darts.isPending}
        markRequired
      />

      {submitted && hasErrors ? (
        <p className="field__error" role="alert">
          Check the highlighted fields and try again.
        </p>
      ) : null}

      <div className="cluster profile-form__actions">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
        {secondaryAction}
      </div>
    </form>
  );
}
