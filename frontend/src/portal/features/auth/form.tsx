/** Shared bits for the auth forms: DRF error plumbing, in one place. */
import { ApiError } from '../../api/client';

/** The message DRF returned for one field, or null. */
export function fieldError(error: unknown, name: string): string | null {
  if (!(error instanceof ApiError)) return null;
  return error.fieldErrors[name] ?? null;
}

export interface FormAlertProps {
  error: unknown;
  /** Fields the form renders itself, so they are not repeated up here. */
  handled?: string[];
}

/**
 * The form-level complaint: a `detail` string, or any field error the form has
 * no input for (a stale reset token, say). Renders nothing when the form is
 * already showing everything the server said.
 */
export function FormAlert({ error, handled = [] }: FormAlertProps) {
  if (!(error instanceof ApiError)) return null;

  const fields = error.fieldErrors;
  const leftover = Object.entries(fields).filter(([name]) => !handled.includes(name));
  const message =
    leftover.length > 0 ? leftover[0]![1] : Object.keys(fields).length === 0 ? error.message : null;

  if (!message) return null;
  return (
    <p className="field__error" role="alert">
      {message}
    </p>
  );
}
