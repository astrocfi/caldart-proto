import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { EmailPreference, EmailPreferenceChange } from '@/portal/api/types';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { EmailPreferencesPage } from './EmailPreferencesPage';

const MISSION: EmailPreference = {
  email_type: 3,
  name: 'Mission',
  description: 'Requests for pilots and aircraft.',
  opted_out: false,
};

const FUNDRAISING: EmailPreference = {
  email_type: 2,
  name: 'Fundraising',
  description: 'Appeals for donations.',
  opted_out: true,
};

/**
 * Serve `rows` from `/me/email-preferences` and apply each `PUT` to them, recording
 * every body the screen sent.
 */
function stubPreferences(rows: EmailPreference[]): EmailPreferenceChange[][] {
  let current = rows;
  const sent: EmailPreferenceChange[][] = [];
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/me/email-preferences`, () => HttpResponse.json(current)),
    http.put(`${API}/me/email-preferences`, async ({ request }) => {
      const body = (await request.json()) as EmailPreferenceChange[];
      sent.push(body);
      current = current.map((row) => {
        const change = body.find((entry) => entry.email_type === row.email_type);
        return change === undefined ? row : { ...row, opted_out: change.opted_out };
      });
      return HttpResponse.json(current);
    }),
  );
  return sent;
}

function renderPage() {
  renderWithProviders(<EmailPreferencesPage />, { route: '/email-preferences' });
}

describe('EmailPreferencesPage', () => {
  it('shows one switch per type, on when the person receives it', async () => {
    stubPreferences([FUNDRAISING, MISSION]);
    renderPage();

    expect(await screen.findByRole('switch', { name: 'Mission' })).toBeChecked();
    expect(screen.getByRole('switch', { name: 'Fundraising' })).not.toBeChecked();
  });

  it('describes each switch by what its type is for', async () => {
    stubPreferences([MISSION]);
    renderPage();

    expect(await screen.findByRole('switch', { name: 'Mission' })).toHaveAccessibleDescription(
      'Requests for pilots and aircraft.',
    );
  });

  it('saves a switch the moment it moves', async () => {
    const sent = stubPreferences([MISSION]);
    renderPage();

    await userEvent.click(await screen.findByRole('switch', { name: 'Mission' }));

    await waitFor(() => expect(sent).toEqual([[{ email_type: 3, opted_out: true }]]));
  });

  it('says Saved once the change lands', async () => {
    stubPreferences([MISSION]);
    renderPage();

    await userEvent.click(await screen.findByRole('switch', { name: 'Mission' }));

    expect(await screen.findByText('Saved.')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Mission' })).not.toBeChecked();
  });

  it('turns a type back on', async () => {
    const sent = stubPreferences([FUNDRAISING]);
    renderPage();

    await userEvent.click(await screen.findByRole('switch', { name: 'Fundraising' }));

    await waitFor(() => expect(sent).toEqual([[{ email_type: 2, opted_out: false }]]));
  });

  it('leaves the switch where it was and says why when the save is refused', async () => {
    server.use(
      signedInAs(makeUser()),
      http.get(`${API}/me/email-preferences`, () => HttpResponse.json([MISSION])),
      http.put(`${API}/me/email-preferences`, () =>
        HttpResponse.json(
          { email_type: ['That email type does not exist, or cannot be turned off.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('switch', { name: 'Mission' }));

    expect(
      await screen.findByText('That email type does not exist, or cannot be turned off.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Mission' })).toBeChecked();
  });

  it('says so when there is nothing to turn off', async () => {
    stubPreferences([]);
    renderPage();

    expect(await screen.findByText('There is nothing to turn off')).toBeInTheDocument();
  });
});
