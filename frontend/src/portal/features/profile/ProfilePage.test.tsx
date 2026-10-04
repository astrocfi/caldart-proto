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
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Enter a phone number.')).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it('moves the focus to the field it refuses, a screen above the button', async () => {
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile({ phone: '' }))),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(screen.getByLabelText(label('Phone'))).toHaveFocus();
  });

  it('keeps the focus on Save changes after a save goes through', async () => {
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('City'));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByText('Profile saved.');

    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' })).toHaveFocus());
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
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText("Enter the medical's expiration date.")).toBeInTheDocument();
  });

  it('clears an inline error as soon as the member fixes it', async () => {
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile({ phone: '' }))),
      http.put(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await screen.findByLabelText(label('Phone'));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByText('Enter a phone number.');

    await userEvent.type(screen.getByLabelText(label('Phone')), '555-0100');

    await waitFor(() =>
      expect(screen.queryByText('Enter a phone number.')).not.toBeInTheDocument(),
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
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

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
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

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
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

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
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('No such county.')).toBeInTheDocument();
    expect(screen.getByText('Check the highlighted fields and try again.')).toBeInTheDocument();
  });

  it('fills the first and last name from the account', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByLabelText(label('First name'))).toHaveValue('Marta');
    expect(screen.getByLabelText(label('Last name'))).toHaveValue('Reyes');
  });

  it('saves edited names with the rest of the profile', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeVerifiedProfile({ last_name: 'Smith' }));
      }),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    const last = await screen.findByLabelText(label('Last name'));
    await user.clear(last);
    await user.type(last, ' SMITH ');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await screen.findByText('Profile saved.');
    expect(body).toMatchObject({ first_name: 'Marta', last_name: 'SMITH' });
  });

  it('shows the stored casing of a name once the save succeeds', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, () =>
        HttpResponse.json(makeVerifiedProfile({ last_name: 'Smith' })),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    const last = await screen.findByLabelText(label('Last name'));
    await user.clear(last);
    await user.type(last, 'SMITH');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(screen.getByLabelText(label('Last name'))).toHaveValue('Smith'));
  });

  it('refuses to save a blank first name and never calls the API', async () => {
    const user = userEvent.setup();
    const save = vi.fn();
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, () => {
        save();
        return HttpResponse.json(makeVerifiedProfile());
      }),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await user.clear(await screen.findByLabelText(label('First name')));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Enter your first name.')).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it('saves the callsign upper case as it was typed', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())),
      http.put(`${API}/me/profile`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeVerifiedProfile({ ham_callsign: 'W6ABC' }));
      }),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    const callsign = await screen.findByLabelText('Amateur radio callsign');
    await user.type(callsign, 'w6abc');
    expect(callsign).toHaveValue('W6ABC');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await screen.findByText('Profile saved.');
    expect(body).toMatchObject({ ham_callsign: 'W6ABC' });
  });

  it('refuses a callsign that is not in US format', async () => {
    const user = userEvent.setup();
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeVerifiedProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });
    await user.type(await screen.findByLabelText('Amateur radio callsign'), 'X1ABC');
    await user.tab();

    expect(
      await screen.findByText('Enter a US amateur radio callsign, such as W6ABC.'),
    ).toBeVisible();
  });

  it('explains itself when the profile cannot be loaded', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json({ detail: 'Server exploded.' }, { status: 500 }),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByText("Your profile didn't load")).toBeInTheDocument();
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

  it('draws no mark under an item the member does not hold, whatever is on file', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeVerifiedProfile({ pilot_certificate_type: 'none', certificate_number: '' }),
        ),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(
      await screen.findByLabelText(label('Pilot certificate')),
    ).not.toHaveAccessibleDescription(/Verified/);
  });

  it('says Expired under a lapsed medical, though somebody verified it', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeVerifiedProfile({ medical_expiration: '2025-02-02' })),
      ),
    );

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByLabelText(label('Medical expires'))).toHaveAccessibleDescription(
      /^Expired\s*Verified by Dana Leader on 05\/01\/2026$/,
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
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

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
