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

beforeEach(() => {
  posted = null;
});

describe('MemberCreatePage', () => {
  it('posts the account and the nested profile together', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'nova@example.org');
    await user.type(screen.getByLabelText('First name'), 'Nova');
    await user.type(screen.getByLabelText('Last name'), 'Ito');
    await user.type(screen.getByLabelText('Phone'), '408-555-0199');
    await user.type(screen.getByLabelText('City'), 'San Jose');
    await user.selectOptions(screen.getByLabelText('Pilot certificate'), 'private');
    await user.click(screen.getByLabelText('Instrument'));
    await user.type(screen.getByLabelText('Administrator notes'), 'Met at the airshow.');

    await user.click(screen.getByRole('button', { name: 'Create member' }));

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

  it('creates a member unless told otherwise', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'plain@example.org');
    await user.click(screen.getByRole('button', { name: 'Create member' }));

    await waitFor(() => expect(posted?.kind).toBe('member'));
  });

  it('creates a friend when the kind says so', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'pal@example.org');
    await user.selectOptions(screen.getByLabelText('Kind of account'), 'friend');
    await user.click(screen.getByRole('button', { name: 'Create member' }));

    await waitFor(() => expect(posted?.kind).toBe('friend'));
  });

  it('omits the password when the box is left blank', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'invited@example.org');
    await user.click(screen.getByRole('button', { name: 'Create member' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted).not.toHaveProperty('password');
  });

  it('sends a password when one is typed', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers());
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'nova@example.org');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Create member' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted?.password).toBe('correct-horse-battery');
  });

  it('goes to the new member record on success', async () => {
    const user = userEvent.setup();
    server.use(...createHandlers(makeDetail({ id: 42 })));
    renderCreate();

    await user.type(screen.getByLabelText(/Email address/), 'nova@example.org');
    await user.click(screen.getByRole('button', { name: 'Create member' }));

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

    await user.type(screen.getByLabelText(/Email address/), 'taken@example.org');
    await user.click(screen.getByRole('button', { name: 'Create member' }));

    expect(
      await screen.findByText('An account with that email address already exists.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Enter a valid phone number.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Email address/)).toHaveAttribute('aria-invalid', 'true');
  });

  it('offers a way back to the list', () => {
    server.use(...createHandlers());
    renderCreate();
    expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute('href', '/admin/members');
  });

  it.each(['Home airport', 'IFR rated', 'Medical expires', 'Last flight review'])(
    'labels %s exactly as the member form does',
    (label) => {
      server.use(...createHandlers());
      renderCreate();
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    },
  );

  it('leaves the profile fields unstarred, so a half-known record can be saved', () => {
    server.use(...createHandlers());
    const { container } = renderCreate();

    const starred = Array.from(container.querySelectorAll('.field__required')).map(
      (marker) => marker.parentElement?.textContent,
    );
    expect(starred).toEqual(['Email address*']);
  });
});
