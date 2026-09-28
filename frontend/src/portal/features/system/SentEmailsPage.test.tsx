import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { systemPageHandlers } from './pageHandlers';
import { SentEmailsPage } from './SentEmailsPage';

describe('SentEmailsPage', () => {
  it('is headed Sent Emails, with its lede', async () => {
    server.use(...systemPageHandlers());
    renderWithProviders(<SentEmailsPage />);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sent Emails' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Every message the site has sent, with who it went to and why.'),
    ).toBeInTheDocument();
  });

  it('holds the email log and nothing else', async () => {
    server.use(...systemPageHandlers());
    renderWithProviders(<SentEmailsPage />);

    expect(await screen.findByText('No emails sent yet')).toBeInTheDocument();
    const titles = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent);
    expect(titles).toEqual(['Email log']);
  });
});
