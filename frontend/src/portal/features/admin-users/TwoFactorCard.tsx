/**
 * The user record's **Two-factor sign-in** card.
 *
 * A dot says whether the account has an authenticator app set up.  **Reset two-factor**,
 * for somebody who lost their phone and their backup codes, asks first, then takes the
 * app and the codes away, signs the person out everywhere, and mails them; they set it up
 * again at their next sign-in.  The reset is offered only while two-factor sign-in is on.
 * Your own record doesn't offer a reset: you change your own on your profile.  A system
 * administrator's record offers it grayed out to anybody who is not one, with the reason.
 */
import type { JSX } from 'react';

import type { AdminUser } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { FormAlert } from '@/portal/features/auth/form';
import './users.css';
import { useAccountStatusAction } from './api';

/** Why Reset two-factor is grayed out on a system administrator's record. */
export const SYSTEM_ADMIN_ONLY =
  "Only a system administrator can reset a system administrator's two-factor sign-in.";

/** What Reset two-factor does, under the button. */
const RESET_HINT =
  'For a lost phone: they set two-factor sign-in up again the next time they sign in.';

export interface TwoFactorCardProps {
  user: AdminUser;
  /** True on your own record, which doesn't offer a reset. */
  isSelf: boolean;
}

/** The **Two-factor sign-in** card: whether it is on, and the reset. */
export function TwoFactorCard({ user, isSelf }: TwoFactorCardProps): JSX.Element {
  const toast = useToast();
  const action = useAccountStatusAction(user.id);
  const isOn = user.two_factor_enabled;
  const isLocked = !user.can_reset_two_factor;

  return (
    <Card title="Two-factor sign-in">
      <div className="stack">
        <p>
          <StatusDot tone={isOn ? 'current' : 'none'} label={isOn ? 'On' : 'Off'} />
        </p>
        {isSelf ? (
          <p className="muted">Change your own two-factor sign-in on your profile.</p>
        ) : null}
        {isSelf || !isOn ? null : (
          <div className="account-actions">
            <div>
              <ConfirmButton
                label="Reset two-factor"
                variant="danger"
                disabled={isLocked}
                choices={[
                  {
                    label: 'Reset two-factor',
                    variant: 'danger',
                    onChoose: () =>
                      action
                        .mutateAsync('reset-two-factor')
                        .then(() => toast.show('Two-factor sign-in reset.', 'success')),
                  },
                ]}
              >
                <p>
                  Their authenticator app and backup codes stop working, they are signed out
                  everywhere, and they are mailed to say so. They set two-factor sign-in up again
                  the next time they sign in. Do this only once you are sure the request came from
                  them.
                </p>
              </ConfirmButton>
              <p className="account-actions__hint muted">
                {isLocked ? SYSTEM_ADMIN_ONLY : RESET_HINT}
              </p>
            </div>
          </div>
        )}
        <FormAlert error={action.error} />
      </div>
    </Card>
  );
}
