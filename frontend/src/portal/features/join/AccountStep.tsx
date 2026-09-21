/** Step 1 — create the account (`POST /auth/register`). */
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { useAuth, useRegister } from '../../auth/useAuth';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Field } from '../../components/Field';
import './join.css';

export interface AccountStepProps {
  onDone: () => void;
}

export function AccountStep({ onDone }: AccountStepProps) {
  const { user, isAuthenticated } = useAuth();
  const register = useRegister();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  if (isAuthenticated && user) {
    return (
      <Card className="join-card join-card--narrow" eyebrow="Step 1 of 4" title="Your account">
        <p>
          You are signed in as <strong>{user.email}</strong>.
        </p>
        <div className="cluster card__footer">
          <Button onClick={onDone}>Continue</Button>
          <Link to="/logout">Use a different account</Link>
        </div>
      </Card>
    );
  }

  const error = register.error instanceof ApiError ? register.error : null;
  const fieldErrors = error?.fieldErrors ?? {};

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    register.mutate(
      {
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      },
      { onSuccess: onDone },
    );
  }

  return (
    <Card className="join-card join-card--narrow" eyebrow="Step 1 of 4" title="Create your account">
      <form onSubmit={handleSubmit} noValidate>
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
          error={fieldErrors.email ?? null}
          hint="This is how you will sign in."
        >
          {(props) => (
            <input
              {...props}
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
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
