/**
 * The user record's **Account status** card.
 *
 * It says whether the account can sign in and whether it is blocked from reactivating,
 * and offers the actions that change that, each asking first: **Deactivate account** or
 * **Reactivate account**, and **Block reactivation** or **Allow reactivation**. Blocking
 * an active account deactivates it as well. Your own account offers neither, since the
 * server refuses both. Every refusal the server gives is drawn in the card.
 */
import type { JSX } from 'react';

import type { AdminUser } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { useToast } from '@/portal/components/Toast';
import { FormAlert } from '@/portal/features/auth/form';
import { useAccountStatusAction } from './api';
import type { AccountStatusAction } from './api';

/** What the card says about the account's status. */
function statusSentence(user: AdminUser): string {
  if (user.reactivation_blocked) {
    return (
      'Deactivated and blocked from reactivating: signing in, a password reset, and ' +
      'registering again are all refused.'
    );
  }
  return user.is_active
    ? 'Active: the account can sign in.'
    : 'Deactivated: the person can reactivate it by signing in or resetting their password.';
}

/** The toast each action shows once it has gone through. */
const DONE: Record<AccountStatusAction, string> = {
  deactivate: 'Account deactivated.',
  reactivate: 'Account reactivated.',
  block: 'Reactivation blocked.',
  unblock: 'Reactivation allowed.',
};

export interface AccountStatusCardProps {
  user: AdminUser;
  /** True on your own record, which offers no action. */
  isSelf: boolean;
}

/** The **Account status** card: the status, and the actions that change it. */
export function AccountStatusCard({ user, isSelf }: AccountStatusCardProps): JSX.Element {
  const toast = useToast();
  const action = useAccountStatusAction(user.id);
  const handleRun = (which: AccountStatusAction) => () =>
    action.mutateAsync(which).then(() => toast.show(DONE[which], 'success'));

  return (
    <Card title="Account status">
      <div className="stack">
        <p>{statusSentence(user)}</p>
        {isSelf ? (
          <p className="muted">You cannot deactivate or block your own account.</p>
        ) : (
          <div className="cluster">
            {user.is_active ? (
              <ConfirmButton
                key="deactivate"
                label="Deactivate account"
                variant="danger"
                choices={[
                  {
                    label: 'Deactivate account',
                    variant: 'danger',
                    onChoose: handleRun('deactivate'),
                  },
                ]}
              >
                <p>
                  They are signed out everywhere and cannot sign in until the account is
                  reactivated. Automatic renewal and any recurring donation are canceled, and a
                  membership with time left is set aside. Nothing is deleted.
                </p>
              </ConfirmButton>
            ) : (
              <ConfirmButton
                key="reactivate"
                label="Reactivate account"
                disabled={user.reactivation_blocked}
                choices={[{ label: 'Reactivate account', onChoose: handleRun('reactivate') }]}
              >
                <p>
                  They can sign in again, and a membership set aside when the account was
                  deactivated resumes if it has time left. Automatic renewal stays off.
                </p>
              </ConfirmButton>
            )}
            {user.reactivation_blocked ? (
              <ConfirmButton
                key="unblock"
                label="Allow reactivation"
                choices={[{ label: 'Allow reactivation', onChoose: handleRun('unblock') }]}
              >
                <p>
                  The account stays deactivated. The person can then reactivate it by signing in or
                  resetting their password.
                </p>
              </ConfirmButton>
            ) : (
              <ConfirmButton
                key="block"
                label="Block reactivation"
                variant="danger"
                choices={[
                  { label: 'Block reactivation', variant: 'danger', onChoose: handleRun('block') },
                ]}
              >
                <p>
                  {user.is_active ? 'The account is deactivated first. ' : ''}Until you allow
                  reactivation again, the person is told the account has been closed whenever they
                  try to sign in, reset their password, or register with this address.
                </p>
              </ConfirmButton>
            )}
          </div>
        )}
        <FormAlert error={action.error} />
      </div>
    </Card>
  );
}
