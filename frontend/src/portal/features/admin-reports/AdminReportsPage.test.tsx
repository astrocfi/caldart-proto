import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs, subscriptionHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AdminReportsPage } from './AdminReportsPage';

describe('AdminReportsPage', () => {
  it('gives an account administrator the subscriptions and the DART rosters', async () => {
    server.use(
      signedInAs(makeUser({ roles: ['member', 'account_admin'] })),
      ...subscriptionHandlers(),
    );
    renderWithProviders(<AdminReportsPage />);

    expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Subscriptions' })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'DART rosters' })).toBeInTheDocument();
  });

  it('gives a treasurer the subscriptions without the DART rosters', async () => {
    const rosterReads: string[] = [];
    server.use(
      signedInAs(makeUser({ roles: ['member', 'treasurer'] })),
      ...subscriptionHandlers(),
      http.get(`${API}/reports/rosters`, ({ request }) => {
        rosterReads.push(request.url);
        return HttpResponse.json([]);
      }),
    );
    renderWithProviders(<AdminReportsPage />);

    expect(await screen.findByText('No reports are sent by email yet')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'DART rosters' })).not.toBeInTheDocument();
    expect(rosterReads).toEqual([]);
  });
});
