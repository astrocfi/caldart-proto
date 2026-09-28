import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  API,
  NONE_VERIFIED,
  NOT_VERIFIED,
  TEST_CSRF_TOKEN,
  makeUser,
  makeVerifiedProfile,
  signedInAs,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { ProfilePage } from './ProfilePage';
import { TEST_DARTS } from '@test/fixtures/profile';

function label(text: string): RegExp {
  // `<Field>` appends an aria-hidden "*" to required labels.
  return new RegExp(`^${text}\\*?$`);
}

describe('<ProfilePage/>', () => {
  beforeEach(() => {
    server.use(
      signedInAs(makeUser()),
      http.get(`${API}/darts`, () => HttpResponse.json(TEST_DARTS)),
    );
  });

  it('fills the form from the saved profile', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByLabelText(label('Phone'))).toHaveValue('650-555-0101');
    expect(screen.getByLabelText(label('City'))).toHaveValue('San Carlos');
    expect(screen.getByLabelText('Instrument')).toBeChecked();
    expect(screen.getByLabelText('CFI')).not.toBeChecked();
    // The DART select can only show the saved value once `/darts` has answered.
    await waitFor(() => expect(screen.getByLabelText(label('DART'))).toHaveValue('1'));
  });

  it('offers the DARTs the catalog returned', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    await screen.findByLabelText(label('Phone'));
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Watsonville (WVI)' })).toBeInTheDocument(),
    );
  });

  it('refuses to save without a phone number and never calls the API', async () => {
    const save = vi.fn();
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile({ phone: '' }))),
      http.put(`${API}/me/profile`, () => {
        save();
        return HttpResponse.json(makeVerifiedProfile());
      }),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    expect(await screen.findByText('A phone number is required.')).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it('reports a medical without an expiration date', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeVerifiedProfile({ medical_type: 'basicmed', medical_expiration: null }),
        ),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    expect(
      await screen.findByText('Give the expiration date of your medical certificate.'),
    ).toBeInTheDocument();
  });

  it('clears an inline error as soon as the member fixes it', async () => {
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile({ phone: '' }))),
      http.put(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    await screen.findByText('A phone number is required.');

    await userEvent.type(screen.getByLabelText(label('Phone')), '555-0100');

    await waitFor(() =>
      expect(screen.queryByText('A phone number is required.')).not.toBeInTheDocument(),
    );
  });

  it('PUTs every field and shows a toast on success', async () => {
    let body: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeVerifiedProfile({ city: 'Napa' }));
      }),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    const city = await screen.findByLabelText(label('City'));
    await userEvent.clear(city);
    await userEvent.type(city, 'Napa');
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    expect(await screen.findByText('Profile saved.')).toBeInTheDocument();
    expect(body).toMatchObject({ city: 'Napa', phone: '650-555-0101', dart_id: 1 });
  });

  it('shows the stored casing as soon as the save succeeds', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, () =>
        HttpResponse.json(makeVerifiedProfile({ city: 'Palo Alto' })),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    const city = await screen.findByLabelText(label('City'));
    await user.clear(city);
    await user.type(city, 'palo ALTO');
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() => expect(screen.getByLabelText(label('City'))).toHaveValue('Palo Alto'));
  });

  it('carries the bootstrapped CSRF token on the save', async () => {
    let sentToken: string | null = null;
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, ({ request }) => {
        sentToken = request.headers.get('X-CSRFToken');
        return HttpResponse.json(makeVerifiedProfile());
      }),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    await screen.findByText('Profile saved.');
    expect(sentToken).toBe(TEST_CSRF_TOKEN);
  });

  it('shows a field error the server sent back, and points the toast at it', async () => {
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, () =>
        HttpResponse.json({ county: 'No such county.' }, { status: 400 }),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    expect(await screen.findByText('No such county.')).toBeInTheDocument();
    expect(screen.getByText('Check the highlighted fields and try again.')).toBeInTheDocument();
  });

  it('explains itself when the profile cannot be loaded', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json({ detail: 'Server exploded.' }, { status: 500 }),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByText('We could not load your profile')).toBeInTheDocument();
  });
});

describe('<ProfilePage/> inline complaints', () => {
  beforeEach(() => {
    server.use(
      signedInAs(makeUser()),
      http.get(`${API}/darts`, () => HttpResponse.json(TEST_DARTS)),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
    );
  });

  it('marks a half-typed phone number as soon as the box is left', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage />, { route: '/profile' });

    const phone = await screen.findByLabelText(label('Phone'));
    await user.clear(phone);
    await user.type(phone, '123');
    await user.tab();

    expect(await screen.findByText('Use a ten-digit number like 415-555-0100.')).toBeVisible();
  });

  it('says nothing about a blank optional field that is passed through', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage />, { route: '/profile' });

    const alternate = await screen.findByLabelText(label('Alternate phone'));
    await user.clear(alternate);
    await user.click(alternate);
    await user.tab();

    expect(screen.queryByText('Use a ten-digit number like 415-555-0100.')).not.toBeInTheDocument();
  });

  it('clears the complaint once the number is finished', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage />, { route: '/profile' });

    const phone = await screen.findByLabelText(label('Phone'));
    await user.clear(phone);
    await user.type(phone, '123');
    await user.tab();
    await screen.findByText('Use a ten-digit number like 415-555-0100.');

    await user.type(phone, '4155550100');

    expect(screen.queryByText('Use a ten-digit number like 415-555-0100.')).not.toBeInTheDocument();
  });

  it('marks the certificate, the medical, and the photo ID with who verified them', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByLabelText(label('Photo ID'))).toHaveValue('passport');
    expect(screen.getByLabelText(label('Medical expires'))).toHaveAccessibleDescription(
      'Verified by Dana Leader on 05/01/2026',
    );
  });

  it('reads Not yet verified for an item nobody has checked', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeVerifiedProfile({ verification: NONE_VERIFIED })),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByLabelText(label('Photo ID'))).toHaveAccessibleDescription(
      'Not yet verified',
    );
  });

  it('shows the medical as not yet verified once a change the member saves clears it', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeVerifiedProfile({
            medical_type: 'second',
            verification: { ...makeVerifiedProfile().verification, medical: NOT_VERIFIED },
          }),
        ),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await user.selectOptions(await screen.findByLabelText(label('Medical')), 'second');
    await user.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() =>
      expect(screen.getByLabelText(label('Medical expires'))).toHaveAccessibleDescription(
        'Not yet verified',
      ),
    );
    expect(screen.getByLabelText(label('Pilot certificate'))).toHaveAccessibleDescription(
      /^Verified by Dana Leader/,
    );
  });
});
