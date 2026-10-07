/**
 * Whether a sent bulk email is on its recipients' Email to me page, with **Hide from
 * Messages** or **Show in Email to me**.
 *
 * Every person a bulk email went to can read it again under Email to me. CalDART
 * management can take one off, such as a callout that no longer applies, after
 * confirming, and put it back at once. Neither changes the email's history, so the
 * Sent page reads the same either way. Only CalDART management sees the control.
 */
import type { JSX } from 'react';

import type { BulkEmailDetail } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { useToast } from '@/portal/components/Toast';
import { hasAnyRole } from '@/portal/nav';
import { useHideFromMessages } from './deliveryApi';
import { actionError } from './SendStatus';

/** What the screen says once the email is hidden. */
export const HIDDEN_MESSAGE = 'The email is hidden from Email to me.';

/** What the screen says once the email is shown again. */
export const SHOWN_MESSAGE = 'The email is back in Email to me.';

/** The Messages line for `email`, which has started sending; nothing for other roles. */
export function MessagesVisibility({ email }: { email: BulkEmailDetail }): JSX.Element | null {
  const { roles } = useAuth();
  const hide = useHideFromMessages(email.id);
  const toast = useToast();
  if (!hasAnyRole(roles, ['management'])) return null;

  const handleShow = (): void => {
    hide.mutate(false, { onSuccess: () => toast.show(SHOWN_MESSAGE, 'success') });
  };

  return (
    <div className="stack-tight">
      {email.hidden_from_archive ? (
        <>
          <p>
            This email is hidden: the people it went to no longer see it under Email to me. Its
            history here is unchanged.
          </p>
          <div className="cluster">
            <Button variant="secondary" onClick={handleShow} disabled={hide.isPending}>
              Show in Email to me
            </Button>
          </div>
        </>
      ) : (
        <>
          <p>Everybody this email went to can read it again under Email to me.</p>
          <div className="cluster">
            <ConfirmButton
              label="Hide from Email to me"
              choices={[
                {
                  label: 'Hide it',
                  variant: 'danger',
                  onChoose: () =>
                    hide.mutateAsync(true).then(() => toast.show(HIDDEN_MESSAGE, 'success')),
                },
              ]}
            >
              <p>
                Nobody it went to will see it under Email to me any more, and the link in their copy
                will no longer open it. Its history here stays as it is, and you can show it again.
              </p>
            </ConfirmButton>
          </div>
        </>
      )}
      {hide.isError ? (
        <p className="field__error" role="alert">
          {actionError(hide.error)}
        </p>
      ) : null}
    </div>
  );
}
