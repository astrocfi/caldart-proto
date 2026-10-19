import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { answerSender, LEADER_SENDER, NO_DART_SENDER } from '@test/fixtures/bulkEmail';
import { makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { RoleSlug } from '@/portal/api/types';
import { OwnSenderNotice, SenderNotice } from './SenderNotice';

describe('SenderNotice', () => {
  it('says why a DART leader without a DART cannot send', () => {
    renderWithProviders(<SenderNotice sender={NO_DART_SENDER} />);
    expect(screen.getByRole('status')).toHaveTextContent(
      "Your profile doesn't name a DART, so you can't send to anybody.",
    );
  });

  it('links to My profile, where the DART is set', () => {
    renderWithProviders(<SenderNotice sender={NO_DART_SENDER} />);
    expect(screen.getByRole('link', { name: 'Open "My profile"' })).toHaveAttribute(
      'href',
      '/profile',
    );
  });

  it("doesn't show anything for a sender who can send", () => {
    const { container } = renderWithProviders(<SenderNotice sender={LEADER_SENDER} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('OwnSenderNotice', () => {
  /** Render the notice for a person holding `roles` whose sender context is `sender`. */
  function renderFor(roles: RoleSlug[], sender = NO_DART_SENDER) {
    server.use(signedInAs(makeUser({ roles })));
    answerSender(sender);
    return renderWithProviders(<OwnSenderNotice />);
  }

  it('tells a DART leader without a DART, wherever it is shown', async () => {
    renderFor(['member', 'dart_leader']);
    expect(await screen.findByRole('link', { name: 'Open "My profile"' })).toBeInTheDocument();
  });

  it("doesn't show anything to a DART leader who has a DART", async () => {
    const calls: string[] = [];
    const record = ({ request }: { request: Request }) => calls.push(request.url);
    server.events.on('request:end', record);
    renderFor(['member', 'dart_leader'], LEADER_SENDER);
    await waitFor(() => expect(calls.some((url) => url.endsWith('/bulk-email/sender'))).toBe(true));
    server.events.removeListener('request:end', record);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it("doesn't ask about a member who doesn't send bulk email", async () => {
    const calls: string[] = [];
    const record = ({ request }: { request: Request }) => calls.push(request.url);
    server.events.on('request:start', record);
    renderFor(['member']);
    await waitFor(() => expect(calls.some((url) => url.endsWith('/auth/me'))).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 20));
    server.events.removeListener('request:start', record);
    expect(calls.some((url) => url.endsWith('/bulk-email/sender'))).toBe(false);
  });
});
