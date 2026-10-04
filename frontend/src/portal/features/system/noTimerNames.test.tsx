/**
 * No System page names a systemd unit, a timer, or systemd itself: the screens
 * say when a job runs in words, and the unit names belong to the server's
 * operator, not to the reader.
 */
import { screen } from '@testing-library/react';
import type { JSX } from 'react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { HealthDatabasePage } from './HealthDatabasePage';
import { systemPageHandlers } from './pageHandlers';
import { ScheduledPage } from './ScheduledPage';
import { SentEmailsPage } from './SentEmailsPage';

/** A unit name such as `caldart-reminders`, the word systemd, or a `.timer` suffix. */
const TIMER_PATTERN = /caldart-[a-z]+|systemd|\.timer/;

const PAGES: [name: string, page: () => JSX.Element, loaded: string][] = [
  ['Health and database', HealthDatabasePage, '0.1.0'],
  ['Sent emails', SentEmailsPage, 'No emails sent yet'],
  ['Scheduled', ScheduledPage, 'No reminders sent yet'],
];

describe('the System pages', () => {
  it.each(PAGES)('%s names no timer', async (_name, Page, loaded) => {
    server.use(...systemPageHandlers());
    const { container } = renderWithProviders(<Page />);

    await screen.findByText(loaded);
    expect(container.textContent).not.toMatch(TIMER_PATTERN);
  });
});
