/** Step 1 — create the account (`POST /auth/register`) as a member or as a friend. */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { PersonKind } from '@/portal/api/types';
import { isVerificationSent, useAuth, useRegister, useSignOut } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { EMAIL_MESSAGE, isEmailAddress, maskEmail } from '@/portal/masks';
import { joinStepEyebrow } from './steps';
import './join.css';

/** The error code `POST /auth/register` answers for a deactivated account's address. */
const DEACTIVATED = 'deactivated';

/** The two kinds of account a visitor may join as, with the words the site uses. */
const KIND_CHOICES: { kind: PersonKind; title: string; description: string }[] = [
  {
    kind: 'member',
    title: 'Join as a member',
    description: 'Pay annual dues now and be counted as a current member.',
  },
  {
    kind: 'friend',
    title: 'Join as a friend',
    description: 'No dues. Support CalDART when you like, and become a member any time.',
  },
];

export interface AccountStepProps {
  onDone: () => void;
}

/**
 * Step 1 of the join wizard: sign in, or register through `useRegister` as a member
 * or as a friend.
 *
 * An address that belongs to a donor signs nobody in: the server mails it a
 * verification link instead, so the step shows the verify step's "Check your email"
 * copy for that address in place of the form.  An address that belongs to a
 * deactivated account is refused, and the refusal comes with a link to the sign-in
 * page, which offers to reactivate it.
 */
export function AccountStep({ onDone: handleDone }: AccountStepProps): JSX.Element {
  const { user, isAuthenticated } = useAuth();
  const { signOut, isPending: isSigningOut } = useSignOut();
  const register = useRegister();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [kind, setKind] = useState<PersonKind>('member');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  if (isAuthenticated && user) {
    return (
      <Card
        className="join-card join-card--narrow"
        eyebrow={joinStepEyebrow('account')}
        title="Your account"
      >
        <p>
          You are signed in as <strong>{user.email}</strong>.
        </p>
        <div className="cluster card__footer">
          <Button onClick={handleDone}>Continue</Button>
          <Button variant="quiet" onClick={() => signOut()} disabled={isSigningOut}>
            Use a different account
          </Button>
        </div>
      </Card>
    );
  }

  if (sentTo !== null) {
    return <VerificationSent email={sentTo} kind={kind} />;
  }

  const error = register.error instanceof ApiError ? register.error : null;
  const fieldErrors = error?.fieldErrors ?? {};
  const isDeactivated = error !== null && errorCode(error) === DEACTIVATED;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Say so here rather than after a round trip: the address is how they
    // will sign in, and a typo in it locks them out of their own account.
    if (!isEmailAddress(email)) {
      setEmailError(EMAIL_MESSAGE);
      return;
    }
    setEmailError(null);
    const address = email.trim();
    register.mutate(
      {
        email: address,
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        kind,
      },
      {
        onSuccess: (result) => {
          if (isVerificationSent(result)) {
            setSentTo(address);
            return;
          }
          handleDone();
        },
      },
    );
  }

  return (
    <Card
      className="join-card join-card--narrow"
      eyebrow={joinStepEyebrow('account')}
      title="Create your account"
    >
      <form onSubmit={handleSubmit} noValidate>
        <fieldset className="join-kind">
          <legend>How would you like to join?</legend>
          {KIND_CHOICES.map((choice) => (
            <label
              key={choice.kind}
              className="join-kind__card"
              data-selected={choice.kind === kind ? 'true' : 'false'}
            >
              <input
                type="radio"
                name="kind"
                value={choice.kind}
                checked={choice.kind === kind}
                onChange={() => setKind(choice.kind)}
              />
              <span className="join-kind__body">
                <span className="join-kind__title">{choice.title}</span>
                <span className="join-kind__description muted">{choice.description}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <Field label="First name" required error={fieldErrors.first_name ?? null}>
          {(props) => (
            <input
              {...props}
              type="text"
              name="first_name"
              autoComplete="given-name"
              required
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
            />
          )}
        </Field>
        <Field label="Last name" required error={fieldErrors.last_name ?? null}>
          {(props) => (
            <input
              {...props}
              type="text"
              name="last_name"
              autoComplete="family-name"
              required
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
            />
          )}
        </Field>
        <Field
          label="Email address"
          required
          error={emailError ?? fieldErrors.email ?? null}
          hint="This is how you will sign in."
        >
          {(props) => (
            <MaskedInput
              {...props}
              type="email"
              name="email"
              autoComplete="email"
              required
              mask={maskEmail}
              value={email}
              onValueChange={(next) => setEmail(next)}
            />
          )}
        </Field>
        <Field
          label="Password"
          required
          error={fieldErrors.password ?? null}
          hint="At least eight characters, and not one of the obvious ones."
        >
          {(props) => (
            <input
              {...props}
              type="password"
              name="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
        </Field>

        {isDeactivated ? (
          <p className="join__aside">
            <Link to={`/login?email=${encodeURIComponent(email.trim())}`}>
              Sign in to reactivate
            </Link>
          </p>
        ) : null}

        {error && Object.keys(fieldErrors).length === 0 ? (
          <p className="field__error" role="alert">
            {error.message}
          </p>
        ) : null}

        <div className="cluster">
          <Button type="submit" disabled={register.isPending}>
            {register.isPending ? 'Creating…' : 'Create account'}
          </Button>
          <Link to="/login?next=%2Fjoin">Already a member? Sign in</Link>
        </div>
      </form>
    </Card>
  );
}

/** The machine-readable `code` an error body carries beside its messages, if any. */
function errorCode(error: ApiError): string | null {
  const body = error.body;
  if (body === null || typeof body !== 'object' || !('code' in body)) return null;
  return typeof body.code === 'string' ? body.code : null;
}

interface VerificationSentProps {
  email: string;
  kind: PersonKind;
}

/**
 * What registering a donor's address shows: the verify step's copy, with nobody
 * signed in, since only following the link turns the donor into an account that
 * can sign in.
 */
function VerificationSent({ email, kind }: VerificationSentProps): JSX.Element {
  return (
    <Card
      className="join-card join-card--narrow"
      eyebrow={joinStepEyebrow('verify', kind)}
      title="Check your email"
    >
      <p>
        We sent a verification message to {email}. Click the link in it to continue setting up your
        account.
      </p>
      <p className="muted">
        Once the address is verified, sign in with the password you just chose.
      </p>
    </Card>
  );
}
