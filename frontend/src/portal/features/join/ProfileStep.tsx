/**
 * Step 3 — the same profile form `/profile` uses, at the same full working width, so
 * its paired fields (a phone number and its extension) sit side by side as they do
 * there.
 */
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { useToast } from '@/portal/components/Toast';
import { ProfileForm } from '@/portal/features/profile/ProfileForm';
import { useProfile, useSaveProfile } from '@/portal/features/profile/api';
import {
  EMPTY_PROFILE_FORM,
  profileToForm,
  saveErrorMessage,
} from '@/portal/features/profile/form';
import { joinStepEyebrow } from './steps';
import './join.css';

export interface ProfileStepProps {
  onDone: () => void;
}

/** Step 3 of the join wizard: the profile form shared with `/profile`. */
export function ProfileStep({ onDone }: ProfileStepProps): JSX.Element {
  const profile = useProfile();
  const save = useSaveProfile();
  const toast = useToast();

  if (profile.isPending) {
    return (
      <Card
        className="join-card join-card--wide"
        eyebrow={joinStepEyebrow('profile')}
        title="About you"
      >
        <p className="muted" role="status">
          Loading your profile…
        </p>
      </Card>
    );
  }

  if (profile.isError) {
    return (
      <Card
        className="join-card join-card--wide"
        eyebrow={joinStepEyebrow('profile')}
        title="About you"
      >
        <EmptyState
          title="Your profile didn't load"
          description={
            profile.error instanceof ApiError
              ? profile.error.message
              : 'Try again in a moment, or contact CalDART if it keeps happening.'
          }
        />
      </Card>
    );
  }

  const serverErrors = save.error instanceof ApiError ? save.error.fieldErrors : undefined;

  return (
    <Card
      className="join-card join-card--wide"
      eyebrow={joinStepEyebrow('profile')}
      title="About you"
    >
      <p className="muted">
        CalDART needs a way to reach you during an activation. Everything except your phone and
        address can wait until later.
      </p>
      <ProfileForm
        initialValues={profile.data ? profileToForm(profile.data) : EMPTY_PROFILE_FORM}
        submitLabel="Save and continue"
        submitting={save.isPending}
        serverErrors={serverErrors}
        serverError={save.error}
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
