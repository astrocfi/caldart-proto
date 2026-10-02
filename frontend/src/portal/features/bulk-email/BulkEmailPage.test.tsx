import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmail, BulkEmailDetail, BulkEmailPreview } from '@/portal/api/types';
import { BulkEmailPage } from './BulkEmailPage';

const PREVIEW: BulkEmailPreview = {
  count: 2,
  skipped_count: 1,
  recipients: [
    { user_id: 1, name: 'Ann Able', email: 'ann@example.org', reason: '' },
    { user_id: 2, name: 'Bea Bell', email: 'bea@example.org', reason: '' },
  ],
  skipped: [
    { user_id: 3, name: 'Gil Gone', email: 'gil@example.org', reason: 'Account deactivated' },
  ],
};

const SENT: BulkEmailDetail = {
  id: 7,
  subject: 'Spring seminar',
  body: 'Join us.',
  filters: { kind: 'friend' },
  sender: 'Grace Holloway',
  created_at: '2026-10-02T17:00:00Z',
  sent_at: '2026-10-02T17:00:05Z',
  sent_count: 1,
  failed_count: 1,
  skipped_count: 1,
  recipients: [
    { user_id: 1, name: 'Ann Able', email: 'ann@example.org', status: 'sent', reason: '' },
    {
      user_id: 2,
      name: 'Bea Bell',
      email: 'bea@example.org',
      status: 'failed',
      reason: 'Refused by the mail server',
    },
    {
      user_id: 3,
      name: 'Gil Gone',
      email: 'gil@example.org',
      status: 'skipped',
      reason: 'Account deactivated',
    },
  ],
};

interface Calls {
  previews: unknown[];
  sends: unknown[];
  historyReads: number;
}

/** Answer the screen's endpoints, recording what the page sent. */
function answerBulkEmail({
  preview = PREVIEW,
  history = [],
}: { preview?: BulkEmailPreview; history?: BulkEmail[] } = {}): Calls {
  const calls: Calls = { previews: [], sends: [], historyReads: 0 };
  server.use(
    http.get(`${API}/darts`, () =>
      HttpResponse.json([{ id: 3, name: 'Bay Area DART', airport_identifiers: 'LVK' }]),
    ),
    http.get(`${API}/bulk-email`, () => {
      calls.historyReads += 1;
      return HttpResponse.json(history);
    }),
    http.post(`${API}/bulk-email/preview`, async ({ request }) => {
      calls.previews.push(await request.json());
      return HttpResponse.json(preview);
    }),
    http.post(`${API}/bulk-email/send`, async ({ request }) => {
      calls.sends.push(await request.json());
      return HttpResponse.json(SENT, { status: 201 });
    }),
  );
  return calls;
}

/** Choose friends, write the message, and press Preview recipients. */
async function composeAndPreview(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Kind' }), 'friend');
  await user.type(screen.getByRole('textbox', { name: /Subject/ }), 'Spring seminar');
  await user.type(screen.getByRole('textbox', { name: /Message/ }), 'Join us.');
  await user.click(screen.getByRole('button', { name: 'Preview recipients' }));
}

describe('BulkEmailPage', () => {
  it('previews the message with the filters that carry a value', async () => {
    const calls = answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);

    await waitFor(() =>
      expect(calls.previews).toEqual([
        { subject: 'Spring seminar', body: 'Join us.', filters: { kind: 'friend' } },
      ]),
    );
  });

  it('counts who would be sent the email and who is skipped', async () => {
    answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);

    expect(await screen.findByRole('status')).toHaveTextContent(
      '2 people will be sent this email; 1 is skipped.',
    );
  });

  it('lists each person, and each skip with its reason', async () => {
    answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);

    const table = await screen.findByRole('table', { name: '3 people' });
    expect(within(table).getByRole('row', { name: /Gil Gone/ })).toHaveTextContent(
      'SkippedGil Gone · gil@example.orgAccount deactivated',
    );
  });

  it('downloads the previewed list with the same filters', async () => {
    answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);

    expect(await screen.findByRole('link', { name: 'Download list' })).toHaveAttribute(
      'href',
      '/api/v1/bulk-email/preview.csv?kind=friend',
    );
  });

  it('shows a refused field under the field', async () => {
    answerBulkEmail();
    server.use(
      http.post(`${API}/bulk-email/preview`, () =>
        HttpResponse.json({ subject: ['Write a subject.'] }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await user.click(await screen.findByRole('button', { name: 'Preview recipients' }));

    expect(await screen.findByRole('textbox', { name: /Subject/ })).toHaveAccessibleDescription(
      'Write a subject.',
    );
  });

  it('offers no send when nobody would be sent a copy', async () => {
    answerBulkEmail({ preview: { count: 0, skipped_count: 0, recipients: [], skipped: [] } });
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);

    await screen.findByRole('status');
    expect(screen.queryByRole('button', { name: /^Send to/ })).not.toBeInTheDocument();
  });

  it('sends nothing until the send is confirmed', async () => {
    const calls = answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await user.click(await screen.findByRole('button', { name: 'Send to 2 people' }));

    expect(screen.getByRole('region', { name: 'Send to 2 people' })).toHaveTextContent(
      'This sends Spring seminar to 2 people now.',
    );
    expect(calls.sends).toEqual([]);
  });

  it('sends the message once confirmed', async () => {
    const calls = answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await user.click(await screen.findByRole('button', { name: 'Send to 2 people' }));
    await user.click(screen.getByRole('button', { name: 'Send now' }));

    await waitFor(() =>
      expect(calls.sends).toEqual([
        { subject: 'Spring seminar', body: 'Join us.', filters: { kind: 'friend' } },
      ]),
    );
  });

  it('shows each person’s result in place of the preview once sent', async () => {
    answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await user.click(await screen.findByRole('button', { name: 'Send to 2 people' }));
    await user.click(screen.getByRole('button', { name: 'Send now' }));

    const results = await screen.findByRole('region', { name: 'Results of Spring seminar' });
    expect([
      within(results).getByRole('status').textContent,
      within(results).getByRole('row', { name: /Bea Bell/ }).textContent,
      screen.queryByRole('button', { name: /^Send to/ }),
    ]).toEqual([
      'Sent 1, failed 1, skipped 1.',
      'FailedBea Bell · bea@example.orgRefused by the mail server',
      null,
    ]);
  });

  it('reads the history again once a send is stored', async () => {
    const calls = answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await user.click(await screen.findByRole('button', { name: 'Send to 2 people' }));
    await user.click(screen.getByRole('button', { name: 'Send now' }));

    await waitFor(() => expect(calls.historyReads).toBe(2));
  });

  it('puts the preview away when a filter changes', async () => {
    answerBulkEmail();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await screen.findByRole('button', { name: 'Send to 2 people' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Kind' }), 'member');

    expect(screen.queryByRole('button', { name: 'Send to 2 people' })).not.toBeInTheDocument();
  });

  it('says so when a send finds nobody to write to', async () => {
    answerBulkEmail();
    server.use(
      http.post(`${API}/bulk-email/send`, () =>
        HttpResponse.json({ filters: ['Nobody matches these filters.'] }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await user.click(await screen.findByRole('button', { name: 'Send to 2 people' }));
    await user.click(screen.getByRole('button', { name: 'Send now' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Nobody matches these filters.');
  });

  it('says nobody matches when the preview finds nobody at all', async () => {
    answerBulkEmail({ preview: { count: 0, skipped_count: 0, recipients: [], skipped: [] } });
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);

    expect(await screen.findByText('Nobody matches these filters')).toBeInTheDocument();
  });

  it('names the filter the server refused, with its message', async () => {
    answerBulkEmail();
    server.use(
      http.post(`${API}/bulk-email/preview`, () =>
        HttpResponse.json({ filters: { expiring_within: ['Enter a number.'] } }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await user.click(await screen.findByRole('button', { name: 'Preview recipients' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Expiring within (days): Enter a number.',
    );
  });

  it('holds every input still while a send is in flight', async () => {
    answerBulkEmail();
    let release: () => void = () => undefined;
    server.use(
      http.post(`${API}/bulk-email/send`, async () => {
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        return HttpResponse.json(SENT, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailPage />);

    await composeAndPreview(user);
    await user.click(await screen.findByRole('button', { name: 'Send to 2 people' }));
    await user.click(screen.getByRole('button', { name: 'Send now' }));

    await waitFor(() =>
      expect(
        [
          screen.getByRole('textbox', { name: /Subject/ }),
          screen.getByRole('textbox', { name: /Message/ }),
          screen.getByRole('combobox', { name: 'Kind' }),
          screen.getByRole('button', { name: 'Preview recipients' }),
        ].map((element) => element.matches(':disabled')),
      ).toEqual([true, true, true, true]),
    );
    release();
    await screen.findByRole('region', { name: 'Results of Spring seminar' });
  });
});
