import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { API, makeUser } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { LoginPage } from '@/portal/features/auth/LoginPage';
import type * as guide from '@/portal/guide';
import { openGuide } from '@/portal/guide';

vi.mock('@/portal/guide', async (importOriginal: () => Promise<typeof guide>) => ({
  ...(await importOriginal()),
  openGuide: vi.fn(),
}));

const EXPIRED = {
  detail: 'Your sign-in has expired. Enter your email address and password again.',
  code: 'mfa_expired',
};

const ENROLLMENT = {
  secret: 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP',
  otpauth_uri: 'otpauth://totp/CalDART:marta%40example.org?secret=JBSWY3DPEHPK3PXP',
  qr_svg: '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
};

const CODES = ['abcde-fghjk', 'mnpqr-stuvw'];

function renderLogin(route = '/login') {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<h1>Dashboard</h1>} />
    </Routes>,
    { route },
  );
}

/** Answer the password with the second factor still owed. */
function passwordAsks(step: 'verify' | 'enroll') {
  return http.post(`${API}/auth/login`, () => HttpResponse.json({ mfa: step }));
}

async function givePassword() {
  await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
  await userEvent.type(screen.getByLabelText(/^password/i), 'correct-horse');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

async function giveCode(code: string) {
  await userEvent.type(await screen.findByLabelText(/^code/i), code);
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('signing in with a code', () => {
  it('asks for a code once the password is right', async () => {
    server.use(passwordAsks('verify'));
    renderLogin();
    await givePassword();

    expect(await screen.findByRole('heading', { name: 'Two-factor sign-in' })).toBeInTheDocument();
  });

  it('says a backup code works in place of the app', async () => {
    server.use(passwordAsks('verify'));
    renderLogin();
    await givePassword();

    expect(await screen.findByText(/enter one of your backup codes instead/i)).toBeInTheDocument();
  });

  it('posts the code and lands on the dashboard', async () => {
    let posted: unknown = null;
    server.use(
      passwordAsks('verify'),
      http.post(`${API}/auth/login/mfa`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(makeUser());
      }),
    );
    renderLogin();
    await givePassword();
    await giveCode('123456');

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(posted).toEqual({ otp: '123456' });
  });

  it('shows a refused code under the box', async () => {
    server.use(
      passwordAsks('verify'),
      http.post(`${API}/auth/login/mfa`, () =>
        HttpResponse.json({ otp: ['That code is not right.'] }, { status: 400 }),
      ),
    );
    renderLogin();
    await givePassword();
    await giveCode('000000');

    expect(await screen.findByText('That code is not right.')).toBeInTheDocument();
  });

  it('goes back to the password with the reason once the sign-in has expired', async () => {
    server.use(
      passwordAsks('verify'),
      http.post(`${API}/auth/login/mfa`, () => HttpResponse.json(EXPIRED, { status: 400 })),
    );
    renderLogin();
    await givePassword();
    await giveCode('000000');

    expect(await screen.findByText(EXPIRED.detail)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('leaves the portal for an admin page named by next', async () => {
    server.use(
      passwordAsks('verify'),
      http.post(`${API}/auth/login/mfa`, () => HttpResponse.json(makeUser())),
    );
    renderLogin('/login?next=%2Fadmin%2Fpages%2F');
    await givePassword();
    await giveCode('123456');

    await waitFor(() => expect(openGuide).toHaveBeenCalledWith('/admin/pages/'));
  });
});

describe('setting up two-factor sign-in while signing in', () => {
  function enrollHandlers() {
    return [
      passwordAsks('enroll'),
      http.post(`${API}/auth/login/mfa/enroll`, () => HttpResponse.json(ENROLLMENT)),
      http.post(`${API}/auth/login/mfa/enroll/confirm`, () =>
        HttpResponse.json({ user: makeUser(), recovery_codes: CODES }),
      ),
    ];
  }

  async function confirmCode() {
    await userEvent.type(await screen.findByLabelText(/^code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Confirm and continue' }));
  }

  it('shows the QR code to scan', async () => {
    server.use(...enrollHandlers());
    renderLogin();
    await givePassword();

    expect(await screen.findByRole('img', { name: /QR code/ })).toBeInTheDocument();
  });

  it('shows the key for typing in by hand, in groups of four', async () => {
    server.use(...enrollHandlers());
    renderLogin();
    await givePassword();

    expect(await screen.findByText('JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP')).toBeInTheDocument();
  });

  it('shows the backup codes once the code is confirmed', async () => {
    server.use(...enrollHandlers());
    renderLogin();
    await givePassword();
    await confirmCode();

    expect(await screen.findByText('abcde-fghjk')).toBeInTheDocument();
  });

  it('waits on the codes until the person says they saved them', async () => {
    server.use(...enrollHandlers());
    renderLogin();
    await givePassword();
    await confirmCode();
    await screen.findByText('abcde-fghjk');
    await userEvent.click(screen.getByRole('button', { name: 'I saved these' }));

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });
});
