import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { MfaStatus } from '@/portal/api/types';
import { REQUIRED_SENTENCE, SecurityCard } from './SecurityCard';

const OFF: MfaStatus = { enabled: false, required_by_role: false, recovery_codes_remaining: 0 };
const ON: MfaStatus = { enabled: true, required_by_role: false, recovery_codes_remaining: 7 };
const REQUIRED: MfaStatus = { ...ON, required_by_role: true };

function renderCard(status: MfaStatus) {
  server.use(http.get(`${API}/auth/mfa`, () => HttpResponse.json(status)));
  return renderWithProviders(<SecurityCard />);
}

describe('<SecurityCard/>', () => {
  it('says two-factor sign-in is off and offers to turn it on', async () => {
    renderCard(OFF);
    expect(await screen.findByRole('button', { name: 'Turn on' })).toBeInTheDocument();
  });

  it('says how many backup codes are left when it is on', async () => {
    renderCard(ON);
    expect(
      await screen.findByText('Two-factor sign-in is on. You have 7 unused backup codes.'),
    ).toBeInTheDocument();
  });

  it('offers to turn it off when no role requires it', async () => {
    renderCard(ON);
    expect(await screen.findByRole('button', { name: 'Turn off' })).toBeInTheDocument();
  });

  it('never offers to turn it off when a role requires it, and says why', async () => {
    renderCard(REQUIRED);
    expect(await screen.findByText(REQUIRED_SENTENCE)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Turn off' })).not.toBeInTheDocument();
  });

  it('turns it on and shows the backup codes', async () => {
    server.use(
      http.post(`${API}/auth/mfa/enroll`, () =>
        HttpResponse.json({ secret: 'ABCDEFGH', otpauth_uri: 'otpauth://x', qr_svg: '<svg/>' }),
      ),
      http.post(`${API}/auth/mfa/enroll/confirm`, () =>
        HttpResponse.json({ recovery_codes: ['abcde-fghjk'] }),
      ),
    );
    renderCard(OFF);
    await userEvent.click(await screen.findByRole('button', { name: 'Turn on' }));
    await userEvent.type(await screen.findByLabelText(/current password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: 'Show the QR code' }));
    await userEvent.type(await screen.findByLabelText(/^code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Turn on two-factor sign-in' }));

    expect(await screen.findByText('abcde-fghjk')).toBeInTheDocument();
  });

  it('asks for the password before drawing a QR code', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/mfa/enroll`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({
          secret: 'ABCDEFGH',
          otpauth_uri: 'otpauth://x',
          qr_svg: '<svg/>',
        });
      }),
    );
    renderCard(OFF);
    await userEvent.click(await screen.findByRole('button', { name: 'Turn on' }));
    await userEvent.type(await screen.findByLabelText(/current password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: 'Show the QR code' }));

    expect(await screen.findByRole('img', { name: /QR code/ })).toBeInTheDocument();
    expect(posted).toEqual({ current_password: 'correct-horse' });
  });

  it('moves the focus to the password box when turning it on', async () => {
    renderCard(OFF);
    await userEvent.click(await screen.findByRole('button', { name: 'Turn on' }));
    expect(await screen.findByLabelText(/current password/i)).toHaveFocus();
  });

  it('makes new backup codes with a current code', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/mfa/recovery-codes`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({ recovery_codes: ['mnpqr-stuvw'] });
      }),
    );
    renderCard(ON);
    await userEvent.click(await screen.findByRole('button', { name: 'New backup codes' }));
    await userEvent.type(await screen.findByLabelText(/^code/i), '654321');
    await userEvent.click(screen.getByRole('button', { name: 'Make new backup codes' }));

    expect(await screen.findByText('mnpqr-stuvw')).toBeInTheDocument();
    expect(posted).toEqual({ otp: '654321' });
  });

  it('turns it off with the password and a code', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/mfa/disable`, async ({ request }) => {
        posted = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderCard(ON);
    await userEvent.click(await screen.findByRole('button', { name: 'Turn off' }));
    await userEvent.type(await screen.findByLabelText(/current password/i), 'correct-horse');
    await userEvent.type(screen.getByLabelText(/^code/i), '111111');
    await userEvent.click(screen.getByRole('button', { name: 'Turn off two-factor sign-in' }));

    await screen.findByText('Two-factor sign-in is off.');
    expect(posted).toEqual({ current_password: 'correct-horse', otp: '111111' });
  });

  it('shows a refused code under the box', async () => {
    server.use(
      http.post(`${API}/auth/mfa/disable`, () =>
        HttpResponse.json({ otp: ['That code is not right.'] }, { status: 400 }),
      ),
    );
    renderCard(ON);
    await userEvent.click(await screen.findByRole('button', { name: 'Turn off' }));
    await userEvent.type(await screen.findByLabelText(/current password/i), 'correct-horse');
    await userEvent.type(screen.getByLabelText(/^code/i), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Turn off two-factor sign-in' }));

    expect(await screen.findByText('That code is not right.')).toBeInTheDocument();
  });
});
