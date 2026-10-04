import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { CalloutSummary } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { answerSender, NO_DART_SENDER } from '@test/fixtures/bulkEmail';
import { makeCalloutSummary } from '@test/fixtures/callouts';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { CALLOUT_COLUMNS, CalloutsPage } from './CalloutsPage';

/** Render the list with `/bulk-email/callouts` answering `rows`. */
function renderList(rows: CalloutSummary[]) {
  server.use(http.get(`${API}/bulk-email/callouts`, () => HttpResponse.json(rows)));
  renderWithProviders(<CalloutsPage />, { route: '/bulk-email/callouts' });
}

describe('CalloutsPage', () => {
  // The state reads twice: once for a screen reader, beside its dot, and once on screen.
  it('lets who sent a callout and its DART give way on a narrow screen', () => {
    expect(
      CALLOUT_COLUMNS.filter((column) => column.dropOrder !== undefined).map(
        (column) => column.key,
      ),
    ).toEqual(['sender', 'dart_name']);
  });

  it('lists each callout with its answers counted', async () => {
    renderList([makeCalloutSummary()]);

    const row = (await screen.findByRole('link', { name: 'Fire near Paradise' })).closest('tr');
    const state = 'Taking answers until 04/08/2026 at 8:30 AM';
    expect(row).toHaveTextContent(
      `Fire near Paradise${formatDate('2026-04-06T17:00:00Z')}${state}Grace Holloway—0102`,
    );
  });

  it('opens a callout on its own page', async () => {
    renderList([makeCalloutSummary()]);

    expect(await screen.findByRole('link', { name: 'Fire near Paradise' })).toHaveAttribute(
      'href',
      '/bulk-email/callouts/7',
    );
  });

  it('says when a closed callout closed, in the site time zone', async () => {
    renderList([makeCalloutSummary({ is_open: false, closed_at: '2026-04-07T16:15:00Z' })]);

    const row = (await screen.findByRole('link', { name: 'Fire near Paradise' })).closest('tr');
    expect(row).toHaveTextContent('Closed 04/07/2026 at 9:15 AM');
  });

  it('says how to send one when there is none', async () => {
    renderList([]);

    expect(await screen.findByText('No callout has been sent')).toBeInTheDocument();
  });

  it('tells a DART leader with no DART why, rather than sending them to Compose', async () => {
    answerSender(NO_DART_SENDER);
    renderList([]);

    expect(await screen.findByRole('link', { name: 'Open My profile' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'New email' })).toBeNull();
  });
});
