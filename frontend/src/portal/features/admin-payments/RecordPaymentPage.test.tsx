import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeDetail, makeFinanceMember } from '@test/fixtures/finance';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RecordPaymentPage } from './RecordPaymentPage';

/** Serve the member search, the plan catalog and the record endpoint. */
function serveRecord(recorded: Record<string, unknown>[], failure?: Record<string, string[]>) {
  server.use(
    http.get(`${API}/plans`, () =>
      HttpResponse.json([
        { slug: 'annual', name: 'Annual', price_cents: 4_500, duration_days: 365, description: '' },
      ]),
    ),
    http.get(`${API}/admin/payments/members`, ({ request }) => {
      const term = new URL(request.url).searchParams.get('search') ?? '';
      return HttpResponse.json(term.length > 0 ? [makeFinanceMember()] : []);
    }),
    http.post(`${API}/admin/payments/record`, async ({ request }) => {
      recorded.push((await request.json()) as Record<string, unknown>);
      if (failure) return HttpResponse.json(failure, { status: 400 });
      return HttpResponse.json(makeDetail(), { status: 201 });
    }),
  );
}

/** Search for a member and choose the one that comes back. */
async function chooseMember(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Member/), 'reyes');
  await user.click(await screen.findByRole('button', { name: /Marta Reyes/ }));
}

describe('RecordPaymentPage', () => {
  it('finds a member by typing part of their name', async () => {
    const user = userEvent.setup();
    serveRecord([]);
    renderWithProviders(<RecordPaymentPage />);

    await user.type(screen.getByLabelText(/Member/), 'reyes');

    expect(await screen.findByRole('button', { name: /Marta Reyes/ })).toBeInTheDocument();
  });

  it('shows the chosen member instead of the search box', async () => {
    const user = userEvent.setup();
    serveRecord([]);
    renderWithProviders(<RecordPaymentPage />);

    await chooseMember(user);

    expect(screen.getByText('marta@example.org')).toBeInTheDocument();
  });

  it('refuses to record a payment with nobody chosen', async () => {
    const user = userEvent.setup();
    const recorded: Record<string, unknown>[] = [];
    serveRecord(recorded);
    renderWithProviders(<RecordPaymentPage />);

    await user.click(screen.getByRole('button', { name: 'Record the payment' }));

    expect(recorded).toHaveLength(0);
  });

  it('says who is missing when nobody was chosen', async () => {
    const user = userEvent.setup();
    serveRecord([]);
    renderWithProviders(<RecordPaymentPage />);

    await user.click(screen.getByRole('button', { name: 'Record the payment' }));

    expect(await screen.findByText('Choose the member this payment is for.')).toBeInTheDocument();
  });

  it('records the check the form was filled in with', async () => {
    const user = userEvent.setup();
    const recorded: Record<string, unknown>[] = [];
    serveRecord(recorded);
    renderWithProviders(<RecordPaymentPage />);

    await chooseMember(user);
    await user.selectOptions(await screen.findByLabelText(/Plan/), 'annual');
    await user.type(screen.getByLabelText(/Reference/), '1041');
    await user.click(screen.getByRole('button', { name: 'Record the payment' }));

    await waitFor(() =>
      expect(recorded[0]).toMatchObject({ user_id: 37, plan: 'annual', reference: '1041' }),
    );
  });

  it('sends the contribution as integer cents', async () => {
    const user = userEvent.setup();
    const recorded: Record<string, unknown>[] = [];
    serveRecord(recorded);
    renderWithProviders(<RecordPaymentPage />);

    await chooseMember(user);
    await user.clear(screen.getByLabelText(/Contribution/));
    await user.type(screen.getByLabelText(/Contribution/), '25.50');
    await user.click(screen.getByRole('button', { name: 'Record the payment' }));

    await waitFor(() => expect(recorded[0]).toMatchObject({ contribution_cents: 2_550 }));
  });

  it('records a contribution with no membership at all', async () => {
    const user = userEvent.setup();
    const recorded: Record<string, unknown>[] = [];
    serveRecord(recorded);
    renderWithProviders(<RecordPaymentPage />);

    await chooseMember(user);
    await user.click(screen.getByRole('button', { name: 'Record the payment' }));

    await waitFor(() => expect(recorded[0]).toMatchObject({ plan: null }));
  });

  it('shows the field the server refused', async () => {
    const user = userEvent.setup();
    serveRecord([], { reference: ['Another payment carries that reference.'] });
    renderWithProviders(<RecordPaymentPage />);

    await chooseMember(user);
    await user.click(screen.getByRole('button', { name: 'Record the payment' }));

    expect(await screen.findByText('Another payment carries that reference.')).toBeInTheDocument();
  });
});
