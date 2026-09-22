/** Step 2 — the same profile form `/profile` uses. */
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { useToast } from '@/portal/components/Toast';
import { ProfileForm } from '../profile/ProfileForm';
import { useProfile, useSaveProfile } from '../profile/api';
import { EMPTY_PROFILE_FORM, profileToForm, saveErrorMessage } from '../profile/form';
import './join.css';

export interface ProfileStepProps {
  onDone: () => void;
}

/** Step 2 of the join wizard: the profile form shared with `/profile`. */
export function ProfileStep({ onDone }: ProfileStepProps): JSX.Element {
  const profile = useProfile();
  const save = useSaveProfile();
  const toast = useToast();

  if (profile.isPending) {
    return (
      <Card className="join-card" eyebrow="Step 2 of 4" title="About you">
        <p className="muted" role="status">
          Loading your profile…
        </p>
      </Card>
    );
  }

  if (profile.isError) {
    return (
      <Card className="join-card" eyebrow="Step 2 of 4" title="About you">
        <EmptyState
          title="We could not load your profile"
          description={
            profile.error instanceof ApiError
              ? profile.error.message
              : 'Something went wrong. Try again in a moment.'
          }
        />
      </Card>
    );
  }

  const serverErrors = save.error instanceof ApiError ? save.error.fieldErrors : undefined;

  return (
    <Card className="join-card" eyebrow="Step 2 of 4" title="About you">
      <p className="muted">
        CalDART needs a way to reach you during an activation. Everything except your phone and
        address can wait until later.
      </p>
      <ProfileForm
        initialValues={profile.data ? profileToForm(profile.data) : EMPTY_PROFILE_FORM}
        submitLabel="Save and continue"
        submitting={save.isPending}
        serverErrors={serverErrors}
        onSubmit={(patch) =>
          save.mutate(patch, {
            onSuccess: onDone,
            onError: (error) => toast.show(saveErrorMessage(error), 'error'),
          })
        }
      />
    </Card>
  );
}
