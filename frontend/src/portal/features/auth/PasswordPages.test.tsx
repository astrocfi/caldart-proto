import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { ChangePasswordPage } from './ChangePasswordPage';
import { ForgotPasswordPage } from './ForgotPasswordPage';
import { ResetPasswordPage } from './ResetPasswordPage';

describe('ForgotPasswordPage', () => {
  it('asks for a link and then says the same thing either way', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/password/reset`, async ({ request }) => {
        posted = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText(/email address/i), 'marta@example.org');
    await userEvent.click(screen.getByRole('button', { name: /email me a link/i }));

    expect(await screen.findByRole('heading', { name: /check your email/i })).toBeInTheDocument();
    expect(screen.getByText(/marta@example.org/)).toBeInTheDocument();
    expect(posted).toEqual({ email: 'marta@example.org' });
  });

  it('shows a validation error without claiming success', async () => {
    server.use(
      http.post(`${API}/auth/password/reset`, () =>
        HttpResponse.json({ email: ['Enter a valid email address.'] }, { status: 400 }),
      ),
    );

    renderWithProviders(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText(/email address/i), 'bogus');
    await userEvent.click(screen.getByRole('button', { name: /email me a link/i }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /check your email/i })).not.toBeInTheDocument();
  });
});

describe('ResetPasswordPage', () => {
  const LINK = '/reset-password?uid=MQ&token=abc-123';

  it('refuses a link with no uid or token', async () => {
    renderWithProviders(<ResetPasswordPage />, { route: '/reset-password' });
    expect(await screen.findByText(/that link is incomplete/i)).toBeInTheDocument();
  });

  it('sends uid and token from the query string', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/password/reset/confirm`, async ({ request }) => {
        posted = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<ResetPasswordPage />, { route: LINK });
    await userEvent.type(screen.getByLabelText(/^new password/i), 'Sierra-Foothills-2027');
    await userEvent.type(screen.getByLabelText(/repeat new password/i), 'Sierra-Foothills-2027');
    await userEvent.click(screen.getByRole('button', { name: /save new password/i }));

    expect(await screen.findByRole('heading', { name: /password changed/i })).toBeInTheDocument();
    expect(posted).toEqual({ uid: 'MQ', token: 'abc-123', new_password: 'Sierra-Foothills-2027' });
  });

  it('catches a mismatch before calling the API', async () => {
    server.use(
      http.post(`${API}/auth/password/reset/confirm`, () => {
        throw new Error('should not be called');
      }),
    );

    renderWithProviders(<ResetPasswordPage />, { route: LINK });
    await userEvent.type(screen.getByLabelText(/^new password/i), 'Sierra-Foothills-2027');
    await userEvent.type(screen.getByLabelText(/repeat new password/i), 'something-else');
    await userEvent.click(screen.getByRole('button', { name: /save new password/i }));

    expect(await screen.findByText(/do not match/i)).toBeInTheDocument();
  });

  it('reports an expired token as a form-level alert', async () => {
    server.use(
      http.post(`${API}/auth/password/reset/confirm`, () =>
        HttpResponse.json(
          { token: ['That password reset link is invalid or has expired.'] },
          {
            status: 400,
          },
        ),
      ),
    );

    renderWithProviders(<ResetPasswordPage />, { route: LINK });
    await userEvent.type(screen.getByLabelText(/^new password/i), 'Sierra-Foothills-2027');
    await userEvent.type(screen.getByLabelText(/repeat new password/i), 'Sierra-Foothills-2027');
    await userEvent.click(screen.getByRole('button', { name: /save new password/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/i);
  });
});

describe('ChangePasswordPage', () => {
  it('sends both passwords and confirms with a toast', async () => {
    server.use(
      signedInAs(makeUser()),
      http.post(`${API}/auth/password/change`, () => new HttpResponse(null, { status: 204 })),
    );

    renderWithProviders(<ChangePasswordPage />);
    await userEvent.type(screen.getByLabelText(/current password/i), 'test-password-123');
    await userEvent.type(screen.getByLabelText(/^new password/i), 'Sierra-Foothills-2027');
    await userEvent.type(screen.getByLabelText(/repeat new password/i), 'Sierra-Foothills-2027');
    await userEvent.click(screen.getByRole('button', { name: /change password/i }));

    expect(await screen.findByText(/your password has been changed/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/current password/i)).toHaveValue('');
  });

  it('shows the API complaint about the current password', async () => {
    server.use(
      signedInAs(makeUser()),
      http.post(`${API}/auth/password/change`, () =>
        HttpResponse.json(
          { current_password: ['That is not your current password.'] },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<ChangePasswordPage />);
    await userEvent.type(screen.getByLabelText(/current password/i), 'wrong');
    await userEvent.type(screen.getByLabelText(/^new password/i), 'Sierra-Foothills-2027');
    await userEvent.type(screen.getByLabelText(/repeat new password/i), 'Sierra-Foothills-2027');
    await userEvent.click(screen.getByRole('button', { name: /change password/i }));

    expect(await screen.findByText('That is not your current password.')).toBeInTheDocument();
  });
});
