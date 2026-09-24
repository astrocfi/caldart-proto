import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RenewalsPanel, renewalRunSummary } from './RenewalsPanel';

const RESULT = { noticed: 2, warned: 0, charged: 1, failed: 0, paused: 0, skipped: 3 };

describe('renewalRunSummary', () => {
  it('says what a rehearsal would have done', () => {
    expect(renewalRunSummary(RESULT, true)).toBe(
      'Would notice 2, warn 0, charge 1, fail 0, pause 0, and skip 3.',
    );
  });

  it('says what a real run did', () => {
    expect(renewalRunSummary(RESULT, false)).toBe(
      'Noticed 2, warned 0, charged 1, failed 0, paused 0, and skipped 3.',
    );
  });
});

describe('RenewalsPanel', () => {
  it('rehearses by default and reports the counts', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/renewals/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(RESULT);
      }),
    );
    renderWithProviders(<RenewalsPanel />);

    expect(screen.getByLabelText('Dry run (charge nothing)')).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByText('Would notice 2, warn 0, charge 1, fail 0, pause 0, and skip 3.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
  });

  it('charges for real once the dry-run box is cleared', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/renewals/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(RESULT);
      }),
    );
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(screen.getByLabelText('Dry run (charge nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByText('Noticed 2, warned 0, charged 1, failed 0, paused 0, and skipped 3.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
  });

  it('reports a run the server refused', async () => {
    server.use(
      http.post(`${API}/system/renewals/run`, () =>
        HttpResponse.json({ detail: 'Stripe is unreachable' }, { status: 502 }),
      ),
    );
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Stripe is unreachable');
  });
});
