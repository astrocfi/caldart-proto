/**
 * The sign-in screen's second-factor steps, shown once the password was right: a code
 * from the authenticator app (or a backup code), or, for an account that must use two-factor
 * sign-in and has no app yet, setting one up and saving the backup codes.
 */
import { useEffect, useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { User } from '@/portal/api/types';
import {
  useAdoptSignedIn,
  useLoginMfa,
  useLoginMfaEnroll,
  useLoginMfaEnrollConfirm,
} from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { focusFirstField } from '@/portal/components/focus';
import { AuthShell } from '@/portal/features/auth/AuthShell';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { EnrollmentForm } from './EnrollmentForm';
import { OtpField } from './OtpField';
import { RecoveryCodesPanel } from './RecoveryCodesPanel';
import { useFocusOnChange } from './focus';

/** The `code` the server gives when the sign-in has to start again with the password. */
const EXPIRED_CODE = 'mfa_expired';

/** True when `error` says the waiting sign-in is gone and the password is needed again. */
export function isSignInExpired(error: unknown): error is ApiError {
  if (!(error instanceof ApiError)) return false;
  const body = error.body as Record<string, unknown> | null;
  return body?.code === EXPIRED_CODE;
}

export interface SecondFactorProps {
  /** The person is signed in: go where they were going. */
  onSignedIn: () => void;
  /** The waiting sign-in is gone; `message` says why, for the password step to show. */
  onExpired: (message: string) => void;
  /** Go back to the password step. */
  onCancel: () => void;
}

/** Asks for a code from the authenticator app, or a backup code, and finishes signing in. */
export function CodeStep({
  onSignedIn,
  onExpired,
  onCancel: handleCancel,
}: SecondFactorProps): JSX.Element {
  const verify = useLoginMfa();
  const [otp, setOtp] = useState('');
  const [missing, setMissing] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // The step replaces the password form, so the focus starts in the code box.
  useEffect(() => {
    focusFirstField(formRef.current);
  }, []);

  useEffect(() => {
    if (isSignInExpired(verify.error)) onExpired(verify.error.message);
  }, [verify.error, onExpired]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (otp.trim() === '') {
      setMissing('Enter the code from your authenticator app, or a backup code.');
      return;
    }
    setMissing(null);
    verify.mutate({ otp }, { onSuccess: onSignedIn });
  };

  return (
    <AuthShell
      title="Two-factor sign-in"
      lede="Enter the code your authenticator app shows for this account."
    >
      <form ref={formRef} noValidate onSubmit={handleSubmit}>
        <OtpField
          value={otp}
          onValueChange={(value) => setOtp(value)}
          error={missing ?? fieldError(verify.error, 'otp')}
        />
        <FormAlert error={verify.error} handled={['otp', 'code']} />
        <div className="auth__actions">
          <Button type="submit" disabled={verify.isPending}>
            {verify.isPending ? 'Checking…' : 'Sign in'}
          </Button>
          <Button variant="quiet" onClick={handleCancel}>
            Start again
          </Button>
        </div>
      </form>
    </AuthShell>
  );
}

/**
 * Sets up an authenticator app while signing in, for an account that must use one:
 * scan, confirm a code, then save the backup codes before going on.
 */
export function EnrollStep({
  onSignedIn,
  onExpired,
  onCancel: handleCancel,
}: SecondFactorProps): JSX.Element {
  const start = useLoginMfaEnroll();
  const confirm = useLoginMfaEnrollConfirm();
  const adopt = useAdoptSignedIn();
  const [saved, setSaved] = useState<{ user: User; codes: string[] } | null>(null);
  const { mutate: startEnrollment } = start;
  const hasStarted = useRef(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  useFocusOnChange(bodyRef, `${String(start.data !== undefined)}:${String(saved !== null)}`);

  // Once per mount: React's development double effect would otherwise draw a second
  // secret, and the QR code shown would stop matching the one the server holds.
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;
    startEnrollment();
  }, [startEnrollment]);

  useEffect(() => {
    const failed = start.error ?? confirm.error;
    if (isSignInExpired(failed)) onExpired(failed.message);
  }, [start.error, confirm.error, onExpired]);

  if (saved !== null) {
    return (
      <AuthShell title="Save your backup codes">
        <div ref={bodyRef}>
          <RecoveryCodesPanel
            codes={saved.codes}
            doneLabel="I saved these"
            onDone={() => {
              adopt(saved.user);
              onSignedIn();
            }}
          />
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Set up two-factor sign-in"
      lede="This account needs a code from an authenticator app each time it signs in. Set one up now to finish signing in."
    >
      <div ref={bodyRef}>
        <EnrollmentForm
          enrollment={start.data}
          startError={start.error}
          isConfirming={confirm.isPending}
          confirmError={confirm.error}
          confirmLabel="Confirm and continue"
          onConfirm={(otp) =>
            confirm.mutate(
              { otp },
              {
                onSuccess: (result) => {
                  setSaved({ user: result.user, codes: result.recovery_codes });
                  start.reset();
                  confirm.reset();
                },
              },
            )
          }
        />
      </div>
      <div className="auth__actions">
        <Button variant="quiet" onClick={handleCancel}>
          Start again
        </Button>
      </div>
    </AuthShell>
  );
}
