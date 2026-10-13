import { useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { MfaEnrollment } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { OtpField } from './OtpField';
import './two-factor.css';

/** The hint under the code box while setting up: the app's code is the only one yet. */
const ENROLL_HINT = 'The six-digit code your authenticator app shows for this account.';

/** The QR code as an image source: the SVG the server drew, as a `data:` URL. */
export function qrSource(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** The secret in groups of four, as an authenticator app's manual entry shows it. */
export function groupedSecret(secret: string): string {
  return secret.match(/.{1,4}/g)?.join(' ') ?? secret;
}

export interface EnrollmentFormProps {
  /** What the app needs, or undefined while the server is drawing it. */
  enrollment: MfaEnrollment | undefined;
  /** Starting enrollment failed: shown in place of the QR code. */
  startError?: unknown;
  /** Confirms the device with the code typed. */
  onConfirm: (otp: string) => void;
  isConfirming: boolean;
  confirmError: unknown;
  /** Words on the confirm button. */
  confirmLabel?: string;
}

/**
 * Setting up an authenticator app: scan the QR code (or type the secret), then type the
 * code the app shows to confirm it.
 */
export function EnrollmentForm({
  enrollment,
  startError,
  onConfirm,
  isConfirming,
  confirmError,
  confirmLabel = 'Turn on two-factor sign-in',
}: EnrollmentFormProps): JSX.Element {
  const [otp, setOtp] = useState('');
  const [missing, setMissing] = useState<string | null>(null);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (otp.trim() === '') {
      setMissing('Enter the code from your authenticator app.');
      return;
    }
    setMissing(null);
    onConfirm(otp);
  };

  if (enrollment === undefined) {
    return startError === undefined || startError === null ? (
      <p className="muted">Preparing your QR code…</p>
    ) : (
      <FormAlert error={startError} />
    );
  }

  return (
    <form className="stack enrollment" noValidate onSubmit={handleSubmit}>
      <ol className="stack enrollment__steps">
        <li>
          Open an authenticator app on your phone, such as Google Authenticator, Microsoft
          Authenticator, 1Password, or Authy, and add an account by scanning this code.
          <img
            className="enrollment__qr"
            src={qrSource(enrollment.qr_svg)}
            alt="QR code to add this account to an authenticator app"
            width={200}
            height={200}
          />
          <p className="muted">
            Cannot scan it? Type this key into the app instead:{' '}
            <code className="enrollment__secret">{groupedSecret(enrollment.secret)}</code>
          </p>
        </li>
        <li>Enter the six-digit code the app shows.</li>
      </ol>
      <OtpField
        value={otp}
        onValueChange={(value) => setOtp(value)}
        hint={ENROLL_HINT}
        isNumeric
        error={missing ?? fieldError(confirmError, 'otp')}
      />
      <FormAlert error={confirmError} handled={['otp', 'code']} />
      <Button type="submit" disabled={isConfirming}>
        {isConfirming ? 'Checking…' : confirmLabel}
      </Button>
    </form>
  );
}
