import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { CalloutSummary } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { makeCalloutSummary } from '@test/fixtures/callouts';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { CalloutsPage } from './CalloutsPage';

/** Render the list with `/bulk-email/callouts` answering `rows`. */
function renderList(rows: CalloutSummary[]) {
  server.use(http.get(`${API}/bulk-email/callouts`, () => HttpResponse.json(rows)));
  renderWithProviders(<CalloutsPage />, { route: '/bulk-email/callouts' });
}

describe('CalloutsPage', () => {
  // The state reads twice: once for a screen reader, beside its dot, and once on screen.
  it('lists each callout with its answers counted', async () => {
    renderList([makeCalloutSummary()]);

    const row = (await screen.findByRole('link', { name: 'Fire near Paradise' })).closest('tr');
    expect(row).toHaveTextContent(
      `Fire near Paradise${formatDate('2026-04-06T17:00:00Z')}Taking answersTaking answersGrace Holloway—0102`,
    );
  });

  it('opens a callout on its own page', async () => {
    renderList([makeCalloutSummary()]);

    expect(await screen.findByRole('link', { name: 'Fire near Paradise' })).toHaveAttribute(
      'href',
      '/bulk-email/callouts/7',
    );
  });

  it('says a closed callout is closed', async () => {
    renderList([makeCalloutSummary({ is_open: false })]);

    const row = (await screen.findByRole('link', { name: 'Fire near Paradise' })).closest('tr');
    expect(row).toHaveTextContent('Closed');
  });

  it('says how to send one when there is none', async () => {
    renderList([]);

    expect(await screen.findByText('No callout has been sent')).toBeInTheDocument();
  });
});
