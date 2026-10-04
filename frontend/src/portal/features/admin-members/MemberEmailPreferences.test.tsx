import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { EmailPreference, EmailPreferenceChange } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { API } from '@test/handlers';
import { makeDetail } from '@test/fixtures/members';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MemberEmailPreferences, showsEmailPreferences } from './MemberEmailPreferences';

const MISSION: EmailPreference = {
  email_type: 3,
  name: 'Mission',
  description: 'Requests for pilots and aircraft.',
  opted_out: false,
  opted_out_source: '',
  opted_out_at: null,
};

const MEMBER = makeDetail({ id: 7, name: 'Marta Reyes' });

/** Serve member 7's preferences, recording every `PUT` body. */
function stubPreferences(rows: EmailPreference[]): EmailPreferenceChange[][] {
  const sent: EmailPreferenceChange[][] = [];
  server.use(
    http.get(`${API}/admin/members/7/email-preferences`, () => HttpResponse.json(rows)),
    http.put(`${API}/admin/members/7/email-preferences`, async ({ request }) => {
      const body = (await request.json()) as EmailPreferenceChange[];
      sent.push(body);
      return HttpResponse.json(
        rows.map((row) => ({ ...row, opted_out: body[0]?.opted_out ?? row.opted_out })),
      );
    }),
  );
  return sent;
}

describe('MemberEmailPreferences', () => {
  it('shows the member’s switches under their name', async () => {
    stubPreferences([MISSION]);
    renderWithProviders(<MemberEmailPreferences member={MEMBER} />);

    expect(
      await screen.findByRole('list', { name: 'Types of email Marta Reyes receives' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Mission' })).toBeChecked();
  });

  it('says who turned a type off and when', async () => {
    const turnedOff: EmailPreference = {
      ...MISSION,
      opted_out: true,
      opted_out_source: 'unsubscribe',
      opted_out_at: '2026-10-03T16:00:00Z',
    };
    stubPreferences([turnedOff]);
    renderWithProviders(<MemberEmailPreferences member={MEMBER} />);

    expect(
      await screen.findByText(
        `Turned off by the member on ${formatDate('2026-10-03T16:00:00Z')} (unsubscribe link).`,
      ),
    ).toBeVisible();
  });

  it('saves a change to the member’s own preferences', async () => {
    const sent = stubPreferences([MISSION]);
    renderWithProviders(<MemberEmailPreferences member={MEMBER} />);

    await userEvent.click(await screen.findByRole('switch', { name: 'Mission' }));

    await waitFor(() => expect(sent).toEqual([[{ email_type: 3, opted_out: true }]]));
    expect(await screen.findByText('Mission turned off.')).toBeInTheDocument();
  });

  it('is shown for a member and a friend', () => {
    expect(showsEmailPreferences(makeDetail({ kind: 'friend' }))).toBe(true);
  });

  it('is not shown for a donor, who receives no bulk email', () => {
    expect(showsEmailPreferences(makeDetail({ kind: 'donor', roles: [] }))).toBe(false);
  });

  it('is not shown on a deleted member’s record', () => {
    expect(showsEmailPreferences(makeDetail({ is_tombstone: true }))).toBe(false);
  });
});
