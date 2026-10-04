import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MemberCreatePage } from './MemberCreatePage';
import { makeDetail } from '@test/fixtures/members';

const DARTS = [{ id: 3, name: 'Palo Alto', airport_identifiers: 'PAO' }];

let posted: Record<string, unknown> | null = null;

function createHandlers(response = makeDetail(), status = 201) {
  return [
    http.get(`${API}/darts`, () => HttpResponse.json(DARTS)),
    http.post(`${API}/admin/members`, async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(response, { status });
    }),
  ];
}

function renderCreate() {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/members/new" element={<MemberCreatePage />} />
      <Route path="/admin/members/:id" element={<p>member record</p>} />
      <Route path="/admin/members" element={<p>member list</p>} />
    </Routes>,
    { route: '/admin/members/new' },
  );
}

/** Type the three boxes an account needs: the address and both names. */
async function fillAccount(user: ReturnType<typeof userEvent.setup>, email: string): Promise<void> {
  await user.type(screen.getByLabelText(/Email address/), email);
  await user.type(screen.getByLabelText(/^First name/), 'Nova');
  await user.type(screen.getByLabelText(/^Last name/), 'Ito');
}

beforeEach(() => {
  posted = null;
});

describe('MemberCreatePage', () => {
  it('posts the account and the nested profile together', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'nova@example.org');
    await user.type(screen.getByLabelText(/^First name/), 'Nova');
    await user.type(screen.getByLabelText(/^Last name/), 'Ito');
    await user.type(screen.getByLabelText('Phone'), '408-555-0199');
    await user.type(screen.getByLabelText('City'), 'San Jose');
    await user.selectOptions(screen.getByLabelText('Pilot certificate'), 'private');
    await user.click(screen.getByLabelText('Instrument'));
    await user.type(screen.getByLabelText('Administrator notes'), 'Met at the airshow.');

    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted).toMatchObject({
      email: 'nova@example.org',
      first_name: 'Nova',
      last_name: 'Ito',
    });
    const profile = posted?.profile as Record<string, unknown>;
    expect(profile.phone).toBe('408-555-0199');
    expect(profile.city).toBe('San Jose');
    expect(profile.pilot_certificate_type).toBe('private');
    expect(profile.ratings).toEqual(['instrument']);
    expect(profile.notes).toBe('Met at the airshow.');
    // Blank date and number fields are sent as null, not as empty strings, and
    // the DART writes as `dart_id` exactly as it does from /me/profile.
    expect(profile.medical_expiration).toBeNull();
    expect(profile.total_hours).toBeNull();
    expect(profile.dart_id).toBeNull();
  });

  it('sends the kind of photo ID with the profile', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'nova@example.org');
    await user.selectOptions(screen.getByLabelText('Photo ID'), 'passport');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect((posted?.profile as Record<string, unknown>).photo_id_type).toBe('passport');
  });

  it('creates a member unless told otherwise', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'plain@example.org');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted?.kind).toBe('member'));
  });

  it('creates a friend when the kind says so', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'pal@example.org');
    await user.selectOptions(screen.getByLabelText('Kind of account'), 'friend');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted?.kind).toBe('friend'));
  });

  it('omits the password when the box is left blank', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'invited@example.org');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted).not.toHaveProperty('password');
  });

  it('sends a password when one is typed', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'nova@example.org');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted?.password).toBe('correct-horse-battery');
  });

  it('goes to the new member record on success', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers(makeDetail({ id: 42 })));
    renderCreate();

    await fillAccount(user, 'nova@example.org');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    expect(await screen.findByText('member record')).toBeInTheDocument();
  });

  it('shows validation errors against the right fields', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/darts`, () => HttpResponse.json(DARTS)),
      http.post(`${API}/admin/members`, () =>
        HttpResponse.json(
          {
            email: ['An account with that email address already exists.'],
            profile: { phone: ['Enter a valid phone number.'] },
          },
          { status: 400 },
        ),
      ),
    );
    renderCreate();

    await fillAccount(user, 'taken@example.org');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    expect(
      await screen.findByText('An account with that email address already exists.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Enter a valid phone number.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Email address/)).toHaveAttribute('aria-invalid', 'true');
  });

  describe('after the server refuses the new member', () => {
    function refuse(): void {
      server.use(
        http.get(`${API}/darts`, () => HttpResponse.json(DARTS)),
        http.post(`${API}/admin/members`, () =>
          HttpResponse.json(
            {
              email: ['An account with that email address already exists.'],
              profile: { phone: ['Enter a valid phone number.'] },
            },
            { status: 400 },
          ),
        ),
      );
    }

    it('moves the focus to the first refused field, far above the button', async () => {
      const user = userEvent.setup();
      refuse();
      renderCreate();

      await fillAccount(user, 'taken@example.org');
      await user.click(screen.getByRole('button', { name: 'Add member' }));

      await waitFor(() => expect(screen.getByLabelText(/Email address/)).toHaveFocus());
    });

    it('says beside the button how many fields to check', async () => {
      const user = userEvent.setup();
      refuse();
      renderCreate();

      await fillAccount(user, 'taken@example.org');
      await user.click(screen.getByRole('button', { name: 'Add member' }));

      expect(await screen.findByText('Check the 2 highlighted fields.')).toBeInTheDocument();
    });

    it('clears the refusal of a field once it is edited', async () => {
      const user = userEvent.setup();
      refuse();
      renderCreate();

      await fillAccount(user, 'taken@example.org');
      await user.click(screen.getByRole('button', { name: 'Add member' }));
      await screen.findByText('An account with that email address already exists.');
      await fillAccount(user, 'x');

      expect(screen.queryByText('An account with that email address already exists.')).toBeNull();
    });
  });

  it('moves the focus to a malformed email address before sending anything', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'not-an-address');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    expect(screen.getByLabelText(/Email address/)).toHaveFocus();
  });

  it('asks for the email address when the box is left empty', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/^First name/), 'Nova');
    await user.type(screen.getByLabelText(/^Last name/), 'Ito');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    expect(screen.getByLabelText(/Email address/)).toHaveAccessibleDescription(
      /Enter their email address\./,
    );
  });

  it('offers a way back to the list', () => {
    server.use(...createHandlers());
    renderCreate();
    expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute('href', '/admin/members');
  });

  it.each(['Home airport', 'Secondary airport', 'Medical expires', 'Last flight review'])(
    'labels %s exactly as the member form does',
    (label) => {
      server.use(...createHandlers());
      renderCreate();
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    },
  );

  it('stars only the address and the names, so a half-known record can be saved', () => {
    server.use(...createHandlers());
    const { container } = renderCreate();

    const starred = Array.from(container.querySelectorAll('.field__required')).map(
      (marker) => marker.parentElement?.textContent,
    );
    expect(starred).toEqual(['Email address*', 'First name*', 'Last name*']);
  });

  it('refuses a member with no first name before anything is sent', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'nova@example.org');
    await user.type(screen.getByLabelText(/^Last name/), 'Ballard');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    expect(await screen.findByText('Enter a first name.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^First name/)).toHaveFocus();
    expect(posted).toBeNull();
  });

  it('adds a member with no phone number, which is optional', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await fillAccount(user, 'nova@example.org');
    await user.click(screen.getByRole('button', { name: 'Add member' }));

    await waitFor(() => expect(posted).not.toBeNull());
  });
});
