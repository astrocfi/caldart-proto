/**
 * The member profile form.
 *
 * One component serves both `/profile` and step 2 of the join wizard.  The
 * fields themselves are `<ProfileFieldsets/>`, shared with the administrator's
 * member screens; what this adds is the state, the inline validation and the
 * submit button a member needs.
 */
import { useState } from 'react';
import type { FormEvent, JSX, ReactNode } from 'react';

import { useDarts } from '@/portal/api/queries';
import type { ProfilePatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
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
  // The fields the member has typed in and left, so a complaint appears when
  // they move on from a field rather than when they try to save.
  const [touched, setTouched] = useState<Partial<Record<keyof ProfileFormValues, true>>>({});
  const [submitted, setSubmitted] = useState(false);
  const darts = useDarts();

  const errors = validateProfileForm(values);

  // Before the first save attempt only a field they have left says anything;
  // afterwards every complaint is shown, including fields never reached.
  const visible: ProfileFormErrors = {};
  for (const [key, message] of Object.entries(errors) as [keyof ProfileFormValues, string][]) {
    if (submitted || touched[key]) visible[key] = message;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(errors).length > 0) return;
    onSubmit(formToPatch(values), values);
  }

  /** Inline rules win; a server message fills in anything they missed. */
  const shownErrors: ProfileFormErrors = { ...serverErrors, ...visible };

  const hasErrors = Object.keys(errors).length > 0;

  return (
    <form onSubmit={handleSubmit} noValidate className="profile-form">
      <ProfileFieldsets
        value={values}
        onChange={(next) => setValues(next)}
        errors={shownErrors}
        darts={darts.data ?? []}
        dartsLoading={darts.isPending}
        markRequired
        onFieldBlur={(key) => setTouched((left) => ({ ...left, [key]: true }))}
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
