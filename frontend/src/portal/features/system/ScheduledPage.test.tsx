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
        'The jobs CalDART runs on a schedule. Run any of them by hand here: each is safe to run ' +
          'twice, and a practice run shows what it would do first.',
      ),
    ).toBeInTheDocument();
  });

  it('puts the reminder emails, their schedule, and renewal charges first, then the rest', async () => {
    renderPage();

    await screen.findByText('No reminders have been sent yet');
    await screen.findByRole('button', { name: 'Save changes' });
    const titles = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent);
    expect(titles).toEqual([
      'Renewal reminder emails',
      'Reminder schedule',
      'Automatic renewal charges',
      'Scheduled reports',
      'Year-end statements',
      'Bounces',
      'Bulk email sender',
    ]);
  });

  it("names each card's Run now for the job it runs", async () => {
    renderPage();

    await screen.findByText('No reminders have been sent yet');
    const names = screen
      .getAllByRole('button', { name: /^Run now: / })
      .map((button) => button.getAttribute('aria-label') ?? button.textContent);
    expect(names).toEqual([
      'Run now: renewal reminder emails',
      'Run now: automatic renewal charges',
      'Run now: scheduled reports',
      'Run now: year-end statements',
      'Run now: bounce check',
      'Run now: bulk email sender',
    ]);
  });

  it('says the reminder emails send email only and never charge', async () => {
    renderPage();

    expect(
      await screen.findByText(
        'The renewal reminder emails go every morning at 7:00 AM to members whose membership ' +
          'is about to expire or has just expired: 60, 30, and 7 days before, on the day, and ' +
          '30 days after. They are email only and never charge anyone, and a member whose ' +
          'automatic renewal is on is skipped.',
      ),
    ).toBeInTheDocument();
  });

  it('says the renewal charges take the money, before the reminder emails', async () => {
    renderPage();

    expect(
      await screen.findByText(
        'The automatic renewal charges run every morning at 6:30 AM, before the reminder ' +
          'emails, so a member they renew is not also reminded. They charge the saved card or ' +
          'PayPal account of every member whose automatic renewal is due, after emailing a ' +
          'notice two weeks ahead and a warning when the card is about to expire.',
      ),
    ).toBeInTheDocument();
  });

  it('says the scheduled reports run every morning', async () => {
    renderPage();

    expect(
      await screen.findByText(
        /^The scheduled reports go every morning at 6:00 AM: every emailed report/,
      ),
    ).toBeInTheDocument();
  });

  it('says the year-end statements run once a year in January', async () => {
    renderPage();

    expect(
      await screen.findByText(
        /^The year-end statements go once a year, on January 15th at 6:45 AM, for the year before\./,
      ),
    ).toBeInTheDocument();
  });

  it("keeps every job's Run now above what its run did", async () => {
    renderPage();

    await screen.findByText('No reminders have been sent yet');
    for (const card of screen.getAllByRole('heading', { level: 2 }).slice(2)) {
      const panel = card.closest('section');
      const results = panel?.querySelector('.job-panel__result');
      const button = panel?.querySelector('.job-panel__run');
      expect(
        button && results
          ? button.compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING
          : 0,
      ).not.toBe(0);
    }
  });
});
