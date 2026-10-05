import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { API, makeUser, makeVerifiedAircraftSummary, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftPickerProps } from '@/portal/features/aircraft';

import type { Aircraft, SiteConfig } from '@/portal/api/types';
import { MyAircraftPage } from './MyAircraftPage';
import { TEST_AIRCRAFT, makeAircraftType, makeProfile } from '@test/fixtures/profile';

/**
 * `<AircraftPicker/>` has its own tests, and driving it means a debounced
 * search against the aircraft endpoints, so stand in for it with one button
 * that selects `PICKED`.  The contract under test is this page's: what it
 * passes down, and what it does with a selection.
 */
const PICKED: Aircraft = {
  id: 9,
  n_number: 'N54321',
  make: 'Piper',
  model: 'Archer',
  type: makeAircraftType({ id: 4, make: 'Piper', model: 'Archer' }),
  category: 'airplane',
  airworthiness: 'standard',
  coverage: { excluded: false, reason: '' },
  year: null,
  owner_type: 'individual',
  owner_name: '',
  owner_contact: '',
  seats: null,
  insurance_carrier: '',
  insurance_policy_number: '',
  insurance_liability_per_occurrence_cents: 0,
  insurance_liability_per_person_cents: 0,
  insurance_hull_cents: null,
  insurance_is_current: false,
  insurance_expiration: null,
  insurance_summary: 'No insurance on file',
  insurance_verification: { verified: false, verified_by: null, verified_at: null },
  updated_at: '2026-09-01T12:00:00Z',
  notes: '',
  created_by: null,
  is_active: true,
};

const excluded = vi.fn<(ids: number[] | undefined) => void>();

/** The site settings My aircraft reads: the address to write to about a record. */
const SITE_CONFIG: SiteConfig = {
  org_name: 'CalDART',
  theme: 'sierra',
  contact_email: 'office@example.org',
  nav: [],
  members_pages: [],
};

vi.mock('@/portal/features/aircraft', async (importOriginal) => {
  // Keep the real module — the editor on this page is built from it — and
  // stand in only for the picker.
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    AircraftPicker: (props: AircraftPickerProps) => {
      excluded(props.excludeIds);
      return (
        <button type="button" onClick={() => props.onSelect(PICKED)}>
          Pick N54321
        </button>
      );
    },
  };
});

describe('<MyAircraftPage/>', () => {
  beforeEach(() => {
    excluded.mockClear();
    server.use(
      signedInAs(makeUser()),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
    );
  });

  it('heads the list Your aircraft', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByRole('heading', { name: 'Your aircraft' })).toBeInTheDocument();
  });

  it('lists an attached aircraft with its insurance in the words every list uses', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [TEST_AIRCRAFT] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByText('N12345')).toBeInTheDocument();
    expect(screen.getByText('Cessna 182T Skylane')).toBeInTheDocument();
    expect(screen.getByText('Insured to 03/01/2027')).toHaveAttribute('data-tone', 'current');
    expect(
      screen.getByText('Liability $1,000,000 per occurrence, $100,000 per person'),
    ).toBeInTheDocument();
  });

  it('ledes with the planes a member commonly flies and nothing more', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByText('The planes you commonly fly.')).toBeInTheDocument();
  });

  it('names the aircraft in the remove control', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [TEST_AIRCRAFT] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByRole('button', { name: 'Remove N12345' })).toHaveAttribute(
      'title',
      'Remove N12345',
    );
  });

  it('flags an aircraft with no insurance on file', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeProfile({
            aircraft: [
              { ...TEST_AIRCRAFT, insurance_is_current: false, insurance_expiration: null },
            ],
          }),
        ),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByText('No insurance on file')).toBeInTheDocument();
  });

  it('states the coverage policy note above the list', async () => {
    server.use(
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
      http.get(`${API}/aircraft/coverage-policy`, () =>
        HttpResponse.json({
          excluded_categories: ['helicopter'],
          excluded_airworthiness: [],
          note: 'Helicopters are not covered.',
        }),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByRole('note', { name: 'Coverage policy' })).toHaveTextContent(
      'Helicopters are not covered.',
    );
  });

  it('shows no note while the policy has none', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [TEST_AIRCRAFT] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    await screen.findByText('N12345');
    expect(screen.queryByRole('note', { name: 'Coverage policy' })).not.toBeInTheDocument();
  });

  it('marks an aircraft the policy excludes, with the reason', async () => {
    const reason = "Not covered: helicopters are excluded by CalDART's policy";
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeProfile({
            aircraft: [
              { ...TEST_AIRCRAFT, category: 'helicopter', coverage: { excluded: true, reason } },
            ],
          }),
        ),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByText('Not covered')).toHaveAttribute('data-tone', 'expired');
    expect(screen.getByText(new RegExp(reason))).toBeInTheDocument();
  });

  it('shows an empty state when nothing is attached', async () => {
    server.use(http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    expect(await screen.findByText('No aircraft yet')).toBeInTheDocument();
  });

  it('tells the picker which aircraft are already attached', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [TEST_AIRCRAFT] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    await screen.findByText('N12345');
    await waitFor(() => expect(excluded).toHaveBeenLastCalledWith([TEST_AIRCRAFT.id]));
  });

  it('attaches the aircraft the picker returns', async () => {
    let posted: unknown = null;
    let attached = false;
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: attached ? [TEST_AIRCRAFT] : [] })),
      ),
      http.post(`${API}/me/profile/aircraft`, async ({ request }) => {
        posted = await request.json();
        attached = true;
        return HttpResponse.json({ aircraft: [TEST_AIRCRAFT] });
      }),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });
    await userEvent.click(await screen.findByRole('button', { name: 'Pick N54321' }));

    expect(await screen.findByText('N54321 added.')).toBeInTheDocument();
    expect(posted).toEqual({ aircraft_id: 9 });
    // The refreshed profile is what the list renders.
    expect(await screen.findByText('N12345')).toBeInTheDocument();
  });

  it('moves the focus to the line of the aircraft just added', async () => {
    const added = { ...TEST_AIRCRAFT, id: 9, n_number: 'N54321' };
    let attached = false;
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: attached ? [added] : [] })),
      ),
      http.post(`${API}/me/profile/aircraft`, () => {
        attached = true;
        return HttpResponse.json({ aircraft: [added] });
      }),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });
    await userEvent.click(await screen.findByRole('button', { name: 'Pick N54321' }));

    await waitFor(() => expect(screen.getByText('N54321').closest('li')).toHaveFocus());
  });

  it('does nothing to an aircraft on the first press of its trashcan', async () => {
    let deleted: string | null = null;
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [TEST_AIRCRAFT] })),
      ),
      http.delete(`${API}/me/profile/aircraft/:id`, ({ params }) => {
        deleted = String(params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });
    await userEvent.click(await screen.findByRole('button', { name: 'Remove N12345' }));

    expect(screen.getByText('N12345')).toBeInTheDocument();
    expect(deleted).toBeNull();
  });

  it('detaches an aircraft once the trashcan is confirmed', async () => {
    let attached = true;
    let deleted: string | null = null;
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: attached ? [TEST_AIRCRAFT] : [] })),
      ),
      http.delete(`${API}/me/profile/aircraft/:id`, ({ params }) => {
        deleted = String(params.id);
        attached = false;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });
    await userEvent.click(await screen.findByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(await screen.findByText('N12345 removed.')).toBeInTheDocument();
    expect(deleted).toBe('7');
    expect(await screen.findByText('No aircraft yet')).toBeInTheDocument();
  });

  it('says so when a detach fails', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [TEST_AIRCRAFT] })),
      ),
      http.delete(`${API}/me/profile/aircraft/:id`, () =>
        HttpResponse.json(
          { detail: "That isn't here. It may have been deleted." },
          { status: 404 },
        ),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });
    await userEvent.click(await screen.findByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(
      await screen.findByText("That isn't here. It may have been deleted."),
    ).toBeInTheDocument();
  });
});

describe('<MyAircraftPage/> editing', () => {
  /** The full register record behind the summary on the profile. */
  function record(createdBy: number | null): Aircraft {
    return {
      ...PICKED,
      id: TEST_AIRCRAFT.id,
      n_number: TEST_AIRCRAFT.n_number,
      make: TEST_AIRCRAFT.make,
      model: TEST_AIRCRAFT.model,
      type: TEST_AIRCRAFT.type,
      insurance_expiration: TEST_AIRCRAFT.insurance_expiration,
      insurance_is_current: TEST_AIRCRAFT.insurance_is_current,
      insurance_summary: TEST_AIRCRAFT.insurance_summary,
      created_by: createdBy,
    };
  }

  beforeEach(() => {
    server.use(
      signedInAs(makeUser({ id: 1 })),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [{ ...TEST_AIRCRAFT, created_by: 1 }] })),
      ),
    );
  });

  it('lets a member correct an aircraft they added themselves', async () => {
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/aircraft/7`, () => HttpResponse.json(record(1))),
      http.patch(`${API}/aircraft/7`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(record(1));
      }),
    );

    renderWithProviders(<MyAircraftPage />);

    await userEvent.click(
      await screen.findByRole('button', { name: `Edit ${TEST_AIRCRAFT.n_number}` }),
    );
    const expiry = await screen.findByLabelText('Insurance expires');
    await userEvent.clear(expiry);
    await userEvent.type(expiry, '2028-05-31');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched).toMatchObject({ insurance_expiration: '2028-05-31' });
    expect(await screen.findByText('N12345 updated.')).toBeInTheDocument();
  });

  it('offers no Edit on a plane somebody else added, and says who to write to', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [{ ...TEST_AIRCRAFT, created_by: 99 }] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />);

    const row = (await screen.findByText('N12345')).closest('li') as HTMLElement;
    expect(within(row).queryByRole('button', { name: /^Edit/ })).not.toBeInTheDocument();
    expect(await within(row).findByRole('link', { name: 'office@example.org' })).toHaveAttribute(
      'href',
      'mailto:office@example.org',
    );
    expect(row).toHaveTextContent('Added by someone else. To correct it, write to');
  });

  it('lets a system administrator edit a plane somebody else added', async () => {
    server.use(
      signedInAs(makeUser({ id: 1, roles: ['member', 'system_admin'] })),
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [{ ...TEST_AIRCRAFT, created_by: 99 }] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />);

    expect(
      await screen.findByRole('button', { name: `Edit ${TEST_AIRCRAFT.n_number}` }),
    ).toBeInTheDocument();
  });

  it('lets an account administrator edit a plane somebody else added', async () => {
    server.use(
      signedInAs(makeUser({ id: 1, roles: ['member', 'account_admin'] })),
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(makeProfile({ aircraft: [{ ...TEST_AIRCRAFT, created_by: 99 }] })),
      ),
    );

    renderWithProviders(<MyAircraftPage />);

    expect(
      await screen.findByRole('button', { name: `Edit ${TEST_AIRCRAFT.n_number}` }),
    ).toBeInTheDocument();
  });

  it.each([
    [true, 'Verified'],
    [false, 'Not yet verified'],
  ])('marks insurance verified=%s as %s', async (verified, mark) => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeProfile({
            aircraft: [makeVerifiedAircraftSummary({ insurance_verified: verified })],
          }),
        ),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    const row = (await screen.findByText('N172SP')).closest('li') as HTMLElement;
    expect(within(row).getByText(mark)).toBeInTheDocument();
  });

  it('leaves an aircraft with no insurance on file without a verification mark', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeProfile({
            aircraft: [
              makeVerifiedAircraftSummary({
                insurance_verified: false,
                insurance_is_current: false,
                insurance_expiration: null,
                insurance_summary: 'No insurance on file',
              }),
            ],
          }),
        ),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    const row = (await screen.findByText('N172SP')).closest('li') as HTMLElement;
    expect(within(row).getByText('No insurance on file')).toBeInTheDocument();
    expect(within(row).queryByText('Not yet verified')).not.toBeInTheDocument();
  });

  it('draws no mark with no insurance on file, even over a stamp left on the record', async () => {
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeProfile({
            aircraft: [
              makeVerifiedAircraftSummary({
                insurance_verified: true,
                insurance_is_current: false,
                insurance_expiration: null,
                insurance_summary: 'No insurance on file',
              }),
            ],
          }),
        ),
      ),
    );

    renderWithProviders(<MyAircraftPage />, { route: '/profile/aircraft' });

    const row = (await screen.findByText('N172SP')).closest('li') as HTMLElement;
    expect(within(row).queryByText('Verified')).not.toBeInTheDocument();
  });

  it('reads the insurance as not yet verified once the member edits it', async () => {
    let edited = false;
    server.use(
      http.get(`${API}/me/profile`, () =>
        HttpResponse.json(
          makeProfile({
            aircraft: [
              makeVerifiedAircraftSummary({
                id: TEST_AIRCRAFT.id,
                n_number: TEST_AIRCRAFT.n_number,
                insurance_verified: !edited,
                created_by: 1,
              }),
            ],
          }),
        ),
      ),
      http.get(`${API}/aircraft/7`, () => HttpResponse.json(record(1))),
      http.patch(`${API}/aircraft/7`, () => {
        edited = true;
        return HttpResponse.json(record(1));
      }),
    );

    renderWithProviders(<MyAircraftPage />);

    expect(await screen.findByText('Verified')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: `Edit ${TEST_AIRCRAFT.n_number}` }));
    await userEvent.type(await screen.findByLabelText('Carrier'), 'AIG');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Not yet verified')).toBeInTheDocument();
  });
});
