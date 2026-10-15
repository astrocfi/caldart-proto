import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { useEmailChangeUndo } from '@/portal/auth/useAuth';
import { Button, ButtonLink } from '@/portal/components/Button';
import { AuthShell } from './AuthShell';

/**
 * What the server says about every unusable undo link, shown too for a link missing its
 * token.
 */
const INVALID_LINK = 'That link is invalid, has expired, or has been used.';

/**
 * `/undo-email-change?token=…` — the page the notice to an account's previous address
 * links to.
 *
 * Undoing ends every session of the account and stops its password from working, so
 * the page asks first and posts the token only when the visitor presses **Undo the
 * change**: a mail scanner that opens the link doesn't undo anything.  It then says what was
 * done and sends the visitor to sign in once they have chosen a new password from the
 * link the server mails.  When the previous address could not be put back, because
 * another account holds it, the account is closed instead, and the page says so and
 * asks the visitor to contact the office.
 */
export function UndoEmailChangePage(): JSX.Element {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const undo = useEmailChangeUndo();

  if (token === '') return <UndoFailed message={INVALID_LINK} />;

  if (undo.isSuccess) {
    const { email, taken } = undo.data;
    if (taken) {
      return (
        <AuthShell title="Account closed">
          <p>
            Your previous address could not be put back, because another account uses it. To keep
            the account safe from whoever moved it to {email}, it has been closed: everybody is
            signed out, its password no longer works, and nobody can sign in, reset its password, or
            reactivate it.
          </p>
          <p>
            Please contact the office, using the address at the bottom of every public page, to get
            it back.
          </p>
        </AuthShell>
      );
    }
    return (
      <AuthShell title="Change undone">
        <p>
          Your sign-in address is {email}. Everybody has been signed out of the account, and its
          password no longer works. We sent {email} a link to choose a new one.
        </p>
        <div className="auth__actions">
          <ButtonLink to={`/login?email=${encodeURIComponent(email)}`}>Go to sign in</ButtonLink>
        </div>
      </AuthShell>
    );
  }

  if (undo.isError) return <UndoFailed message={failureMessage(undo.error)} />;

  return (
    <AuthShell
      title="Undo the change of address?"
      lede="If you did not ask to change your account's address, undo it here."
    >
      <p>
        Undoing puts your previous address back, signs everybody out of the account, and stops its
        password from working. We then email your previous address a link to choose a new one.
      </p>
      <div className="auth__actions">
        <Button onClick={() => undo.mutate({ token })} disabled={undo.isPending}>
          {undo.isPending ? 'Undoing…' : 'Undo the change'}
        </Button>
      </div>
    </AuthShell>
  );
}

/** The server's reason for refusing the link, or the one message for any other failure. */
function failureMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return INVALID_LINK;
  return error.fieldErrors.token ?? error.message;
}

function UndoFailed({ message }: { message: string }): JSX.Element {
  return (
    <AuthShell title="Change not undone">
      <p className="field__error" role="alert">
        {message}
      </p>
      <p>
        <Link to="/forgot-password">Forgot your password?</Link>
      </p>
    </AuthShell>
  );
}
