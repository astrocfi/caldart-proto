import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { MailDeliveryCheck, MailDeliveryFinding } from '@/portal/api/types';
import { formatDateAt } from '@/portal/components/DateText';
import { MailDeliveryPage, summarize } from './MailDeliveryPage';

const CHECK_URL = `${API}/mail/delivery-check`;

function finding(overrides: Partial<MailDeliveryFinding> = {}): MailDeliveryFinding {
  return {
    name: 'Approved senders (SPF)',
    status: 'pass',
    detail: 'SPF is a list of the servers allowed to send CalDART email. It is in place.',
    fix: '',
    ...overrides,
  };
}

function report(findings: MailDeliveryFinding[], overrides: Partial<MailDeliveryCheck> = {}) {
  return { domain: 'example.org', checked_at: '2026-10-03T15:00:00Z', findings, ...overrides };
}

function serve(payload: MailDeliveryCheck) {
  server.use(http.get(CHECK_URL, () => HttpResponse.json(payload)));
}

describe('summarize', () => {
  it('says every check is good when none has a problem or a warning', () => {
    expect(summarize([finding(), finding({ name: 'Other' })])).toBe(
      'Every check is good. Receiving mail systems have what they need to trust email from CalDART.',
    );
  });

  it('counts the warnings when there is no problem', () => {
    expect(summarize([finding(), finding({ status: 'warn' })])).toBe(
      'Email can be delivered, but 1 of 2 checks could be better.',
    );
  });

  it('counts the problems first, and says what they cost', () => {
    expect(summarize([finding({ status: 'fail' }), finding({ status: 'warn' }), finding()])).toBe(
      '1 of 3 checks found a problem. Some email may be marked as spam or not arrive until it is fixed.',
    );
  });
});

describe('MailDeliveryPage', () => {
  it('shows one row per finding with its status in words and its explanation', async () => {
    serve(
      report([
        finding(),
        finding({ name: 'Message signature (DKIM)', status: 'warn', detail: 'No selector.' }),
        finding({ name: 'Bounce address', status: 'fail', detail: 'It is elsewhere.' }),
      ]),
    );
    renderWithProviders(<MailDeliveryPage />);

    const rows = await screen.findAllByRole('listitem');

    expect(rows).toHaveLength(3);
    expect(
      screen.getByRole('heading', { name: /^Good\s*Approved senders \(SPF\)$/ }),
    ).toBeVisible();
    expect(screen.getByRole('heading', { name: /^Warning\s*Message signature/ })).toBeVisible();
    expect(screen.getByRole('heading', { name: /^Problem\s*Bounce address$/ })).toBeVisible();
  });

  it('reads out each status as its word, not as a color', async () => {
    serve(report([finding({ status: 'fail' })]));
    renderWithProviders(<MailDeliveryPage />);

    const heading = await screen.findByRole('heading', { name: /Approved senders/ });

    expect(within(heading).getAllByText('Problem')).toHaveLength(2);
  });

  it('keeps the dot and the word together, apart from the name', async () => {
    serve(report([finding({ status: 'fail' })]));
    renderWithProviders(<MailDeliveryPage />);

    const heading = await screen.findByRole('heading', { name: /Approved senders/ });

    expect(heading.querySelector('.delivery-check__status')).toHaveTextContent('Problem');
  });

  it('says what the record is for in the finding detail', async () => {
    serve(report([finding()]));
    renderWithProviders(<MailDeliveryPage />);

    expect(
      await screen.findByText(/a list of the servers allowed to send CalDART email/),
    ).toBeVisible();
  });

  it('gives the fix of a finding that needs one, and none for a good one', async () => {
    serve(
      report([
        finding({ status: 'fail', fix: 'Ask whoever manages the DNS to add a TXT record.' }),
        finding({ name: 'Bounce address' }),
      ]),
    );
    renderWithProviders(<MailDeliveryPage />);

    await screen.findByText('Ask whoever manages the DNS to add a TXT record.');

    expect(screen.getAllByText(/What to do:/)).toHaveLength(1);
  });

  it('shows when and for which domain the check was made', async () => {
    serve(report([finding()], { checked_at: '2026-10-03T15:00:00Z' }));
    renderWithProviders(<MailDeliveryPage />);

    expect(
      await screen.findByText(`Checked ${formatDateAt('2026-10-03T15:00:00Z')} for example.org.`),
    ).toBeVisible();
  });

  it('summarizes the result above the rows', async () => {
    serve(report([finding({ status: 'warn' })]));
    renderWithProviders(<MailDeliveryPage />);

    expect(
      await screen.findByText('Email can be delivered, but 1 of 1 checks could be better.'),
    ).toBeVisible();
  });

  it('looks again with refresh when Check again is pressed, and shows the new answer', async () => {
    const refreshes: (string | null)[] = [];
    server.use(
      http.get(CHECK_URL, ({ request }) => {
        const refresh = new URL(request.url).searchParams.get('refresh');
        refreshes.push(refresh);
        return HttpResponse.json(
          refresh === 'true'
            ? report([finding({ status: 'pass' })], { checked_at: '2026-10-03T16:30:00Z' })
            : report([finding({ status: 'fail', detail: 'Missing.' })]),
        );
      }),
    );
    renderWithProviders(<MailDeliveryPage />);
    await screen.findByText('Missing.');

    await userEvent.click(screen.getByRole('button', { name: 'Check again' }));

    await waitFor(() => {
      expect(screen.queryByText('Missing.')).not.toBeInTheDocument();
    });
    expect(refreshes).toEqual([null, 'true']);
  });

  it('disables Check again while it is checking', async () => {
    serve(report([finding()]));
    server.use(
      http.get(CHECK_URL, async ({ request }) => {
        if (new URL(request.url).searchParams.has('refresh')) {
          await new Promise((resolve) => setTimeout(resolve, 200));
        }
        return HttpResponse.json(report([finding()]));
      }),
    );
    renderWithProviders(<MailDeliveryPage />);
    await screen.findByRole('list');

    await userEvent.click(screen.getByRole('button', { name: 'Check again' }));

    expect(await screen.findByRole('button', { name: 'Checking…' })).toBeDisabled();
  });

  it('tells the reader when the check could not be run again', async () => {
    serve(report([finding()]));
    renderWithProviders(<MailDeliveryPage />);
    await screen.findByRole('list');
    server.use(http.get(CHECK_URL, () => HttpResponse.json({ detail: 'Boom.' }, { status: 500 })));

    await userEvent.click(screen.getByRole('button', { name: 'Check again' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The check could not be run again. Try once more in a minute.',
    );
  });

  it('shows the error when the first check fails', async () => {
    server.use(http.get(CHECK_URL, () => HttpResponse.json({ detail: 'No.' }, { status: 403 })));
    renderWithProviders(<MailDeliveryPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('No.');
  });
});
