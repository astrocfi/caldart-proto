/**
 * The user record's **Password** card.
 *
 * **Send password reset** emails the person a one-time link, for somebody who has
 * forgotten their password; it waits for a deactivated account to be reactivated.
 * **Require a new password** asks first, then makes the current password stop working,
 * signs the account out everywhere, and emails a link to choose a new one, for an
 * account somebody else may have the password to. It works on a deactivated account,
 * which stays deactivated until its owner follows the link. Your own record offers it
 * not, since **Change password** is yours. A donor's record leaves the card out.
 */
import type { JSX } from 'react';

import type { AdminUser } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { useToast } from '@/portal/components/Toast';
import { FormAlert } from '@/portal/features/auth/form';
import './users.css';
import { useRequireNewPassword, useSendPasswordReset } from './api';

/** What Require a new password does, under the button. */
const REQUIRE_HINT =
  'For an account somebody else may know the password to: signs them out everywhere and ' +
  'emails a link to choose a new password.';

/** Why your own record offers no Require a new password. */
const REQUIRE_SELF_HINT = 'To change your own password, use Change password.';

/** What happens to the account's status, in the confirmation, by where it stands. */
function statusNote(user: AdminUser): string {
  if (user.reactivation_blocked) {
    return (
      'The account is blocked from reactivating, so no email is sent. Once you allow ' +
      'reactivation, they can ask for a reset link from the sign-in page.'
    );
  }
  if (!user.is_active) {
    return 'The account stays deactivated until they follow the link, which brings it back.';
  }
  return '';
}

export interface PasswordCardProps {
  user: AdminUser;
  /** True on your own record, which offers no Require a new password. */
  isSelf: boolean;
}

/** The **Password** card: send a reset link, or require a new password. */
export function PasswordCard({ user, isSelf }: PasswordCardProps): JSX.Element {
  const toast = useToast();
  const sendReset = useSendPasswordReset(user.id);
  const requireNew = useRequireNewPassword(user.id);

  return (
    <Card title="Password">
      <div className="stack">
        <div className="account-actions">
          <div>
            <Button
              variant="secondary"
              disabled={sendReset.isPending || !user.is_active}
              onClick={() =>
                sendReset.mutate(undefined, {
                  onSuccess: (result) => toast.show(result.detail, 'success'),
                  onError: (error) => toast.show(error.message, 'error'),
                })
              }
            >
              {sendReset.isPending ? 'Sending…' : 'Send password reset'}
            </Button>
            <p className="account-actions__hint muted">
              {user.is_active
                ? 'Emails a one-time link so they can choose a new password. You never see it.'
                : 'Reactivate the account before sending a reset link.'}
            </p>
          </div>
          <div>
            {isSelf ? null : (
              <ConfirmButton
                label="Require a new password"
                variant="danger"
                choices={[
                  {
                    label: 'Require a new password',
                    variant: 'danger',
                    onChoose: () =>
                      requireNew
                        .mutateAsync()
                        .then((result) => toast.show(result.detail, 'success')),
                  },
                ]}
              >
                <p>
                  The current password stops working, for them and for anybody else who knows it,
                  and every browser signed in to the account is signed out at once. They are emailed
                  a link to choose a new password. {statusNote(user)}
                </p>
              </ConfirmButton>
            )}
            <p className="account-actions__hint muted">
              {isSelf ? REQUIRE_SELF_HINT : REQUIRE_HINT}
            </p>
          </div>
        </div>
        <FormAlert error={requireNew.error} />
      </div>
    </Card>
  );
}
