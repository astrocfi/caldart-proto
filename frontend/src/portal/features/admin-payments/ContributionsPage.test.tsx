import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ContributionRow } from '@/portal/api/types';
import { ContributionsPage } from './ContributionsPage';
import { statementUrl } from './api';

const MARTA: ContributionRow = {
  user_id: 37,
  name: 'Marta Reyes',
  email: 'marta@example.org',
  count: 2,
  contribution_cents: 11000,
  refunded_cents: 2500,
  net_contribution_cents: 8500,
};

/** Answer the contributions call, recording the year it was asked for. */
function contributionsHandler(rows: ContributionRow[], seen: string[]) {
  return http.get(`${API}/admin/payments/contributions`, ({ request }) => {
    seen.push(new URL(request.url).searchParams.get('year') ?? '');
    return HttpResponse.json(rows);
  });
}

describe('ContributionsPage', () => {
  it('shows what a member gave, what went back and the difference', async () => {
    server.use(contributionsHandler([MARTA], []));
    renderWithProviders(<ContributionsPage />);

    const row = within(await screen.findByRole('row', { name: /Marta Reyes/ }));
    expect(row.getByText('$110.00')).toBeInTheDocument();
    expect(row.getByText('$25.00')).toBeInTheDocument();
    expect(row.getByText('$85.00')).toBeInTheDocument();
  });

  it('offers each member their statement for the year on screen', async () => {
    server.use(contributionsHandler([MARTA], []));
    renderWithProviders(<ContributionsPage />);

    const row = within(await screen.findByRole('row', { name: /Marta Reyes/ }));
    expect(row.getByRole('link', { name: 'Statement' })).toHaveAttribute(
      'href',
      statementUrl(37, new Date().getFullYear()),
    );
  });

  it("leaves the year to the server's own current year, then asks for the one chosen", async () => {
    const seen: string[] = [];
    server.use(contributionsHandler([MARTA], seen));
    renderWithProviders(<ContributionsPage />);
    await screen.findByRole('row', { name: /Marta Reyes/ });

    const thisYear = new Date().getFullYear();
    expect(seen).toEqual(['']);

    await userEvent.selectOptions(screen.getByLabelText('Year'), String(thisYear - 1));

    await expect.poll(() => seen.at(-1)).toBe(String(thisYear - 1));
  });

  it('reads the year from the address, for the table, the statements and the caption', async () => {
    const seen: string[] = [];
    server.use(contributionsHandler([MARTA], seen));
    renderWithProviders(<ContributionsPage />, {
      route: '/admin/payments/contributions?year=2024',
    });

    const row = within(await screen.findByRole('row', { name: /Marta Reyes/ }));
    expect(row.getByRole('link', { name: 'Statement' })).toHaveAttribute(
      'href',
      statementUrl(37, 2024),
    );
    expect(screen.getByRole('table', { name: 'Contributions in 2024' })).toBeInTheDocument();
  });

  it('points the exports at the contributions report for the year chosen', async () => {
    server.use(contributionsHandler([MARTA], []));
    renderWithProviders(<ContributionsPage />, {
      route: '/admin/payments/contributions?year=2024',
    });
    await screen.findByRole('row', { name: /Marta Reyes/ });

    expect(screen.getByRole('link', { name: 'Export PDF' })).toHaveAttribute(
      'href',
      `${API}/reports/contributions/export.pdf?year=2024`,
    );
  });

  it('says so when nobody gave anything that year', async () => {
    server.use(contributionsHandler([], []));
    renderWithProviders(<ContributionsPage />);

    expect(await screen.findByText('No contributions that year')).toBeInTheDocument();
  });

  it('shows a failed call as a failure, not as a year nobody gave in', async () => {
    server.use(
      http.get(
        `${API}/admin/payments/contributions`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    );
    renderWithProviders(<ContributionsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The contributions could not be loaded.',
    );
  });
});
