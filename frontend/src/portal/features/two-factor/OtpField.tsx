import type { JSX } from 'react';

import { Field } from '@/portal/components/Field';

/** What the code box is called wherever a code is asked for. */
export const OTP_LABEL = 'Code';

/** The hint under the box: a backup code is always accepted in place of the app's code. */
export const OTP_HINT =
  'The six-digit code your authenticator app shows. Lost your phone? Enter one of your ' +
  'backup codes instead.';

export interface OtpFieldProps {
  value: string;
  onValueChange: (value: string) => void;
  error?: string | null;
  /** The hint under the box; `OTP_HINT` when left out. */
  hint?: string;
  /** Offer a number pad, where only the app's six digits are taken (setting it up). */
  isNumeric?: boolean;
}

/**
 * The box a two-factor code is typed into.  It takes an authenticator code or a backup
 * code, so it is a text box rather than a number, and the browser is asked to offer a
 * one-time code from the device.
 */
export function OtpField({
  value,
  onValueChange,
  error,
  hint = OTP_HINT,
  isNumeric = false,
}: OtpFieldProps): JSX.Element {
  return (
    <Field label={OTP_LABEL} required hint={hint} error={error}>
      {(props) => (
        <input
          {...props}
          type="text"
          name="otp"
          inputMode={isNumeric ? 'numeric' : 'text'}
          autoComplete="one-time-code"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
        />
      )}
    </Field>
  );
}
