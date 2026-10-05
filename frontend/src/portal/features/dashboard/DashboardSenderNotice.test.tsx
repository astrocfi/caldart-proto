import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { answerSender, NO_DART_SENDER } from '@test/fixtures/bulkEmail';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { MembershipDetail, SiteConfig } from '@/portal/api/types';
import { DashboardPage } from './DashboardPage';

const SITE_CONFIG: SiteConfig = {
  org_name: 'CalDART',
  theme: 'sierra',
  contact_email: 'info@example.org',
  nav: [],
  members_pages: [],
};

const MEMBERSHIP: MembershipDetail = {
  status: 'current',
  expires_on: '2027-06-01',
  plan: 'Annual',
  is_lifetime: false,
  history: [],
};

describe('<DashboardPage/> for a DART leader with no DART', () => {
  it('says bulk email needs a DART, with the way to My profile', async () => {
    server.use(
      signedInAs(makeUser({ roles: ['member', 'dart_leader'] })),
      http.get(`${API}/me/membership`, () => HttpResponse.json(MEMBERSHIP)),
      http.get(`${API}/me/payments`, () => HttpResponse.json([])),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
    );
    answerSender(NO_DART_SENDER);
    renderWithProviders(<DashboardPage />, { route: '/' });

    expect(
      await screen.findByText(/^Bulk email needs a DART\. Set yours on My profile\./),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open My profile' })).toHaveAttribute(
      'href',
      '/profile',
    );
  });
});
