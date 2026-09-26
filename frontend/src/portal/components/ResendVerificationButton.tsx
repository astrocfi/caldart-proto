/** The "Resend verification message" control the join wizard and the dashboard share. */
import type { UseMutationResult } from '@tanstack/react-query';
import type { JSX } from 'react';

import type { VerificationSentResult } from '@/portal/api/types';
import { useResendVerification } from '../auth/useAuth';
import { Button } from './Button';
import type { ButtonVariant } from './Button';
import { useToast } from './Toast';

export interface ResendVerificationButtonProps {
  variant?: ButtonVariant;
  /** Disable the control beyond its own pending state, such as for a deactivated account. */
  disabled?: boolean;
  /**
   * Send through this mutation instead of the signed-in caller's own
   * `POST /auth/email/resend`, such as an administrator resending to another account.
   */
  mutation?: UseMutationResult<VerificationSentResult, Error, void>;
}

/**
 * Mails a fresh verification link and toasts the server's answer, `Verification
 * message sent to <email>.`, or the reason it refused (an address already verified,
 * a deactivated account, or too many requests).
 *
 * Sends through `POST /auth/email/resend` for the signed-in user by default; pass
 * `mutation` to send through a different endpoint instead.
 */
export function ResendVerificationButton({
  variant = 'secondary',
  disabled = false,
  mutation,
}: ResendVerificationButtonProps): JSX.Element {
  const ownResend = useResendVerification();
  const resend = mutation ?? ownResend;
  const toast = useToast();

  return (
    <Button
      variant={variant}
      disabled={disabled || resend.isPending}
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
