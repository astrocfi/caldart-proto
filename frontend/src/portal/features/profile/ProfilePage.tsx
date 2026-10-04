/**
 * `/profile` — the member's own details, the kind of account they hold, and the way to
 * deactivate it.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { KindCard } from '@/portal/features/dashboard/KindSwitch';
import { DeactivateCard } from './DeactivateCard';
import { ProfileForm } from './ProfileForm';
import { useProfile, useSaveProfile } from './api';
import { profileToForm, saveErrorMessage } from './form';

/** Renders and saves the signed-in member's own profile. */
export function ProfilePage(): JSX.Element {
  const profile = useProfile();
  const save = useSaveProfile();
  const toast = useToast();
  // Bumped on every successful save, so the form starts again from what the server
  // stored (a name, street, or city it title-cased, say) rather than from what was typed.
  const [formResetKey, setFormResetKey] = useState(0);
  // The form starts again after a save, which takes the focus off Save profile; it goes
  // back to the button of the form drawn afresh.
  const formCardRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (formResetKey === 0) return;
    formCardRef.current?.querySelector<HTMLElement>('button[type="submit"]')?.focus();
  }, [formResetKey]);

  if (profile.isPending) {
    return (
      <Page title="My profile">
        <p className="muted" role="status">
          Loading your profile…
        </p>
      </Page>
    );
  }

  if (profile.isError || !profile.data) {
    return (
      <Page title="My profile">
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
  const { verification } = profile.data;

  return (
    <Page
      title="My profile"
      lede="CalDART uses these details to reach you during an activation and to check you are current to fly."
      actions={
        <ButtonLink to="/profile/aircraft" variant="secondary">
          My aircraft
        </ButtonLink>
      }
    >
      <div ref={formCardRef}>
        <Card>
          <ProfileForm
            key={formResetKey}
            initialValues={profileToForm(profile.data)}
            verification={verification}
            withNames
            submitting={save.isPending}
            serverErrors={serverErrors}
            serverError={save.error}
            onSubmit={(patch) =>
              save.mutate(patch, {
                onSuccess: () => {
                  setFormResetKey((key) => key + 1);
                  toast.show('Profile saved.', 'success');
                },
                onError: (error) => toast.show(saveErrorMessage(error), 'error'),
              })
            }
          />
        </Card>
      </div>

      <KindCard />

      <p className="muted">
        The planes you commonly fly are kept on <Link to="/profile/aircraft">My aircraft</Link>.
      </p>

      <DeactivateCard />
    </Page>
  );
}
