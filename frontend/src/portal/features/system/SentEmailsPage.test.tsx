import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { systemPageHandlers } from './pageHandlers';
import { SentEmailsPage } from './SentEmailsPage';

describe('SentEmailsPage', () => {
  it('is headed Sent emails, with its lede', async () => {
    server.use(...systemPageHandlers());
    renderWithProviders(<SentEmailsPage />);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sent emails' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Every message the site has sent, with who it went to and why.'),
    ).toBeInTheDocument();
  });

  it('holds the email log and nothing else', async () => {
    server.use(...systemPageHandlers());
    renderWithProviders(<SentEmailsPage />);

    expect(await screen.findByText('No emails sent yet')).toBeInTheDocument();
    expect(document.querySelectorAll('section.card')).toHaveLength(1);
  });

  it('carries no second heading under the page title', async () => {
    server.use(...systemPageHandlers());
    renderWithProviders(<SentEmailsPage />);

    expect(await screen.findByText('No emails sent yet')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument();
  });
});
