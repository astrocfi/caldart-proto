import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { systemPageHandlers } from './pageHandlers';
import { ScheduledPage } from './ScheduledPage';

/** Render the page with every request it makes on mount answered. */
function renderPage(): void {
  server.use(...systemPageHandlers());
  renderWithProviders(<ScheduledPage />);
}

describe('ScheduledPage', () => {
  it('is headed Scheduled, with its lede', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { level: 1, name: 'Scheduled' })).toBeInTheDocument();
    expect(
      screen.getByText(
        'The jobs the server runs on a schedule. Each one can be run by hand here, and a dry ' +
          'run shows what it would do.',
      ),
    ).toBeInTheDocument();
  });

  it('puts the reminder emails and the renewal charges first, then reports and statements', async () => {
    renderPage();

    await screen.findByText('No reminders sent yet');
    const titles = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent);
    expect(titles).toEqual([
      'Renewal reminder emails',
      'Automatic renewal charges',
      'Scheduled reports',
      'Year-end statements',
    ]);
  });

  it('says the reminder emails send email only and never charge', async () => {
    renderPage();

    expect(
      await screen.findByText(
        'Emails members whose membership is about to expire or has just expired: 60, 30, and ' +
          '7 days before, on the day, and 30 days after. It sends email only and never charges ' +
          'anyone. A member whose automatic renewal is on is skipped. It runs every morning; ' +
          'running it again is harmless, because each member gets each reminder once per ' +
          'membership.',
      ),
    ).toBeInTheDocument();
  });

  it('says the renewal charges take the money, before the reminder emails', async () => {
    renderPage();

    expect(
      await screen.findByText(
        'Charges the saved card or PayPal account of every member whose automatic renewal is ' +
          'due, after emailing a notice two weeks ahead and a warning when the card is about ' +
          'to expire. It runs every morning before the reminder emails, so a member it renews ' +
          'is not also reminded. Running it again is harmless: every scheduled charge records ' +
          'what has already gone out.',
      ),
    ).toBeInTheDocument();
  });

  it('says the scheduled reports run every morning', async () => {
    renderPage();

    expect(
      await screen.findByText(/^The sender runs every morning\. It emails every report/),
    ).toBeInTheDocument();
  });

  it('says the year-end statements run once a year in January', async () => {
    renderPage();

    expect(
      await screen.findByText(/^The sender runs once a year in January, for the year before\./),
    ).toBeInTheDocument();
  });
});
