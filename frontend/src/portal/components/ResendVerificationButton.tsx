/** The "Resend verification message" control the join wizard and the dashboard share. */
import type { JSX } from 'react';

import { useResendVerification } from '../auth/useAuth';
import { Button } from './Button';
import type { ButtonVariant } from './Button';
import { useToast } from './Toast';

export interface ResendVerificationButtonProps {
  variant?: ButtonVariant;
}

/**
 * Mails the signed-in user a fresh verification link through `POST /auth/email/resend`
 * and toasts the server's answer, `Verification message sent to <email>.`, or the
 * reason it refused (an address already verified, or too many requests).
 */
export function ResendVerificationButton({
  variant = 'secondary',
}: ResendVerificationButtonProps): JSX.Element {
  const resend = useResendVerification();
  const toast = useToast();

  return (
    <Button
      variant={variant}
      disabled={resend.isPending}
      onClick={() =>
        resend.mutate(undefined, {
          onSuccess: (result) => toast.show(result.detail, 'success'),
          onError: (error) => toast.show(error.message, 'error'),
        })
      }
    >
      Resend verification message
    </Button>
  );
}
