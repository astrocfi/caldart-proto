import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { API, TEST_CSRF_TOKEN, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { ProfilePage } from './ProfilePage';
import { TEST_DARTS, makeProfile } from '@test/fixtures/profile';

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
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    expect(await screen.findByLabelText(label('Phone'))).toHaveValue('650-555-0101');
    expect(screen.getByLabelText(label('City'))).toHaveValue('San Carlos');
    expect(screen.getByLabelText('Instrument')).toBeChecked();
    expect(screen.getByLabelText('CFI')).not.toBeChecked();
    // The DART select can only show the saved value once `/darts` has answered.
    await waitFor(() => expect(screen.getByLabelText(label('DART'))).toHaveValue('1'));
  });

  it('offers the DARTs the catalog returned', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));

    renderWithProviders(<ProfilePage />, { route: '/profile' });

    await screen.findByLabelText(label('Phone'));
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Watsonville (WVI)' })).toBeInTheDocument(),
    );
  });

  it('refuses to save without a phone number and never calls the API', async () => {
    const save = vi.fn();
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ phone: '' }))),
      http.put(`${API}/me/profile`, () => {
        save();
        return HttpResponse.json(makeProfile());
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
        HttpResponse.json(makeProfile({ medical_type: 'basicmed', medical_expiration: null })),
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
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ phone: '' }))),
      http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
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
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
      http.put(`${API}/me/profile`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeProfile({ city: 'Napa' }));
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

  it('carries the bootstrapped CSRF token on the save', async () => {
    let sentToken: string | null = null;
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
      http.put(`${API}/me/profile`, ({ request }) => {
        sentToken = request.headers.get('X-CSRFToken');
        return HttpResponse.json(makeProfile());
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
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
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
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
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
});
