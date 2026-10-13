/**
 * The **Two-factor sign-in** card on `/profile`.
 *
 * It says whether two-factor sign-in is on and how many backup codes are left, and
 * offers what fits: **Turn on** (the password, then scan a QR code, confirm a code, and
 * save the backup codes),
 * **New backup codes** (with a current code), and **Turn off** (with the password and a
 * current code).  A role that requires two-factor sign-in is never offered **Turn off**;
 * the card says why instead.
 */
import { useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import {
  useConfirmMfaEnrollment,
  useDisableMfa,
  useMfaStatus,
  useRegenerateRecoveryCodes,
  useStartMfaEnrollment,
} from './api';
import { EnrollmentForm } from './EnrollmentForm';
import { OtpField } from './OtpField';
import { RecoveryCodesPanel } from './RecoveryCodesPanel';
import { useFocusOnChange } from './focus';

/** Why a role that requires two-factor sign-in has no Turn off button. */
export const REQUIRED_SENTENCE =
  'Your role requires two-factor sign-in, so it cannot be turned off. If you lose your ' +
  'phone, sign in with a backup code, or ask a user administrator to reset it.';

/** What the card is doing: showing the status, or one of its three forms. */
type Mode = 'status' | 'enroll' | 'regenerate' | 'disable' | 'codes';

/** What the card says about the status. */
function statusSentence(enabled: boolean, remaining: number): string {
  if (!enabled) {
    return (
      'Two-factor sign-in is off. Turn it on to be asked for a code from an authenticator ' +
      'app on your phone each time you sign in, as well as your password.'
    );
  }
  const left = remaining === 1 ? '1 unused backup code' : `${remaining} unused backup codes`;
  return `Two-factor sign-in is on. You have ${left}.`;
}

/** The profile's **Two-factor sign-in** card. */
export function SecurityCard(): JSX.Element {
  const status = useMfaStatus();
  const [mode, setMode] = useState<Mode>('status');
  const [codes, setCodes] = useState<string[]>([]);
  const start = useStartMfaEnrollment();
  const confirm = useConfirmMfaEnrollment();
  const toast = useToast();
  const bodyRef = useRef<HTMLDivElement>(null);
  const isShowingQr = start.data !== undefined;
  useFocusOnChange(bodyRef, `${mode}:${String(isShowingQr)}`);

  // Leaving a mode forgets what its requests answered, the secret and the codes included.
  const goTo = (next: Mode) => {
    start.reset();
    confirm.reset();
    if (next !== 'codes') setCodes([]);
    setMode(next);
  };

  const showCodes = (fresh: string[]) => {
    start.reset();
    confirm.reset();
    setCodes(fresh);
    setMode('codes');
  };

  let body: JSX.Element;
  if (status.data === undefined) {
    body = status.isError ? <FormAlert error={status.error} /> : <p className="muted">Loading…</p>;
  } else if (mode === 'enroll') {
    body = (
      <div className="stack">
        {isShowingQr ? (
          <EnrollmentForm
            enrollment={start.data}
            isConfirming={confirm.isPending}
            confirmError={confirm.error}
            onConfirm={(otp) =>
              confirm.mutate(
                { otp },
                {
                  onSuccess: (result) => {
                    toast.show('Two-factor sign-in is on.', 'success');
                    showCodes(result.recovery_codes);
                  },
                },
              )
            }
          />
        ) : (
          <PasswordForm
            submitLabel="Show the QR code"
            isPending={start.isPending}
            error={start.error}
            onSubmit={(password) => start.mutate({ current_password: password })}
          />
        )}
        <Button variant="quiet" onClick={() => goTo('status')}>
          Cancel
        </Button>
      </div>
    );
  } else if (mode === 'codes') {
    body = <RecoveryCodesPanel codes={codes} onDone={() => goTo('status')} />;
  } else if (mode === 'regenerate') {
    body = <RegenerateForm onDone={(fresh) => showCodes(fresh)} onCancel={() => goTo('status')} />;
  } else if (mode === 'disable') {
    body = (
      <DisableForm
        onDone={() => {
          toast.show('Two-factor sign-in is off.', 'success');
          goTo('status');
        }}
        onCancel={() => goTo('status')}
      />
    );
  } else {
    const { enabled, required_by_role: isRequired } = status.data;
    body = (
      <div className="stack">
        <p>{statusSentence(enabled, status.data.recovery_codes_remaining)}</p>
        {isRequired ? <p className="muted">{REQUIRED_SENTENCE}</p> : null}
        <div className="cluster">
          {enabled ? null : <Button onClick={() => goTo('enroll')}>Turn on</Button>}
          {enabled ? (
            <Button variant="secondary" onClick={() => goTo('regenerate')}>
              New backup codes
            </Button>
          ) : null}
          {enabled && !isRequired ? (
            <Button variant="danger" onClick={() => goTo('disable')}>
              Turn off
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <Card title="Two-factor sign-in">
      <div ref={bodyRef}>{body}</div>
    </Card>
  );
}

interface PasswordFormProps {
  submitLabel: string;
  isPending: boolean;
  error: unknown;
  onSubmit: (password: string) => void;
}

/** Asks for the current password before a secret is drawn for a new device. */
function PasswordForm({
  submitLabel,
  isPending,
  error,
  onSubmit: handlePassword,
}: PasswordFormProps): JSX.Element {
  const [password, setPassword] = useState('');

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    handlePassword(password);
  };

  return (
    <form className="stack" noValidate onSubmit={handleSubmit}>
      <p>Confirm it is you, then scan a QR code with an authenticator app on your phone.</p>
      <Field label="Current password" required error={fieldError(error, 'current_password')}>
        {(props) => (
          <input
            {...props}
            type="password"
            name="current_password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        )}
      </Field>
      <FormAlert error={error} handled={['current_password']} />
      <div className="cluster">
        <Button type="submit" disabled={password === '' || isPending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

interface RegenerateFormProps {
  onDone: (codes: string[]) => void;
  onCancel: () => void;
}

/** Asks for a current code, then replaces every backup code. */
function RegenerateForm({
  onDone: handleDone,
  onCancel: handleCancel,
}: RegenerateFormProps): JSX.Element {
  const regenerate = useRegenerateRecoveryCodes();
  const [otp, setOtp] = useState('');

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    regenerate.mutate({ otp }, { onSuccess: (result) => handleDone(result.recovery_codes) });
  };

  return (
    <form className="stack" noValidate onSubmit={handleSubmit}>
      <p>A new set replaces every backup code you have now, used or not.</p>
      <OtpField
        value={otp}
        onValueChange={(value) => setOtp(value)}
        error={fieldError(regenerate.error, 'otp')}
      />
      <FormAlert error={regenerate.error} handled={['otp']} />
      <div className="cluster">
        <Button type="submit" disabled={otp.trim() === '' || regenerate.isPending}>
          Make new backup codes
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

interface DisableFormProps {
  onDone: () => void;
  onCancel: () => void;
}

/** Asks for the password and a current code, then turns two-factor sign-in off. */
function DisableForm({
  onDone: handleDone,
  onCancel: handleCancel,
}: DisableFormProps): JSX.Element {
  const disable = useDisableMfa();
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    disable.mutate({ current_password: password, otp }, { onSuccess: () => handleDone() });
  };

  return (
    <form className="stack" noValidate onSubmit={handleSubmit}>
      <p>You will sign in with your password alone, and your backup codes stop working.</p>
      <Field
        label="Current password"
        required
        error={fieldError(disable.error, 'current_password')}
      >
        {(props) => (
          <input
            {...props}
            type="password"
            name="current_password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        )}
      </Field>
      <OtpField
        value={otp}
        onValueChange={(value) => setOtp(value)}
        error={fieldError(disable.error, 'otp')}
      />
      <FormAlert error={disable.error} handled={['current_password', 'otp']} />
      <div className="cluster">
        <Button
          type="submit"
          variant="danger"
          disabled={password === '' || otp.trim() === '' || disable.isPending}
        >
          Turn off two-factor sign-in
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
