/** `/profile` — the member's own details. */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { DeactivateCard } from './DeactivateCard';
import { ProfileForm } from './ProfileForm';
import { useProfile, useSaveProfile } from './api';
import { profileToForm, saveErrorMessage } from './form';

/** Renders and saves the signed-in member's own profile. */
export function ProfilePage(): JSX.Element {
  const profile = useProfile();
  const save = useSaveProfile();
  const toast = useToast();

  if (profile.isPending) {
    return (
      <Page title="My profile" eyebrow="Membership">
        <p className="muted" role="status">
          Loading your profile…
        </p>
      </Page>
    );
  }

  if (profile.isError || !profile.data) {
    return (
      <Page title="My profile" eyebrow="Membership">
        <EmptyState
          title="We could not load your profile"
          description={
            profile.error instanceof ApiError
              ? profile.error.message
              : 'Something went wrong. Try again in a moment.'
          }
        />
      </Page>
    );
  }

  const serverErrors = save.error instanceof ApiError ? save.error.fieldErrors : undefined;

  return (
    <Page
      title="My profile"
      eyebrow="Membership"
      lede="CalDART uses these details to reach you during an activation and to check you are current to fly."
      actions={
        <ButtonLink to="/profile/aircraft" variant="secondary">
          My aircraft
        </ButtonLink>
      }
    >
      <Card>
        <ProfileForm
          initialValues={profileToForm(profile.data)}
          submitting={save.isPending}
          serverErrors={serverErrors}
          onSubmit={(patch) =>
            save.mutate(patch, {
              onSuccess: () => toast.show('Profile saved.', 'success'),
              onError: (error) => toast.show(saveErrorMessage(error), 'error'),
            })
          }
        />
      </Card>

      <p className="muted">
        The planes you commonly fly are kept on <Link to="/profile/aircraft">My aircraft</Link>.
      </p>

      <DeactivateCard />
    </Page>
  );
}
