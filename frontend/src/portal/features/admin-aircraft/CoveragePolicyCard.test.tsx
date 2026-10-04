import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftCoveragePolicy } from '@/portal/api/types';
import { CoveragePolicyCard } from './CoveragePolicyCard';

const HELICOPTERS: AircraftCoveragePolicy = {
  excluded_categories: ['helicopter'],
  excluded_airworthiness: [],
  note: 'Helicopters are not covered.',
};

/** Answer `GET /aircraft/coverage-policy` with `policy`. */
function servePolicy(policy: AircraftCoveragePolicy): void {
  server.use(http.get(`${API}/aircraft/coverage-policy`, () => HttpResponse.json(policy)));
}

describe('<CoveragePolicyCard/>', () => {
  it('reads out what the policy excludes and its note', async () => {
    servePolicy(HELICOPTERS);

    renderWithProviders(<CoveragePolicyCard />);

    const excluded = await screen.findByText('Excluded categories');
    expect(excluded.nextElementSibling).toHaveTextContent('Helicopter');
    expect(screen.getByText('Helicopters are not covered.')).toBeInTheDocument();
  });

  it('reads an empty list as None', async () => {
    servePolicy(HELICOPTERS);

    renderWithProviders(<CoveragePolicyCard />);

    const airworthiness = await screen.findByText('Excluded airworthiness');
    expect(airworthiness.nextElementSibling).toHaveTextContent('None');
  });

  it('saves the exclusions and the note it is given', async () => {
    servePolicy(HELICOPTERS);
    let sent: AircraftCoveragePolicy | null = null;
    server.use(
      http.put(`${API}/aircraft/coverage-policy`, async ({ request }) => {
        const body = (await request.json()) as AircraftCoveragePolicy;
        sent = body;
        return HttpResponse.json(body);
      }),
    );
    const user = userEvent.setup();

    renderWithProviders(<CoveragePolicyCard />);
    await user.click(await screen.findByRole('button', { name: 'Edit policy' }));
    await user.click(screen.getByRole('button', { name: /Excluded airworthiness/ }));
    await user.click(
      within(screen.getByRole('group', { name: 'Excluded airworthiness' })).getByRole('checkbox', {
        name: 'Experimental',
      }),
    );
    const note = screen.getByRole('textbox', { name: /Note to members/ });
    await user.clear(note);
    await user.type(note, 'Rotorcraft and homebuilts are not covered.');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await screen.findByRole('button', { name: 'Edit policy' });
    expect(sent).toEqual({
      excluded_categories: ['helicopter'],
      excluded_airworthiness: ['experimental'],
      note: 'Rotorcraft and homebuilts are not covered.',
    });
  });

  it('shows the server’s refusal of the note', async () => {
    servePolicy(HELICOPTERS);
    server.use(
      http.put(`${API}/aircraft/coverage-policy`, () =>
        HttpResponse.json(
          { note: ['Ensure this field has no more than 1000 characters.'] },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();

    renderWithProviders(<CoveragePolicyCard />);
    await user.click(await screen.findByRole('button', { name: 'Edit policy' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(
      await screen.findByText('Ensure this field has no more than 1000 characters.'),
    ).toBeInTheDocument();
  });

  it('puts the stored policy back on Cancel', async () => {
    servePolicy(HELICOPTERS);
    const user = userEvent.setup();

    renderWithProviders(<CoveragePolicyCard />);
    await user.click(await screen.findByRole('button', { name: 'Edit policy' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByText('Helicopters are not covered.')).toBeInTheDocument();
  });
});
