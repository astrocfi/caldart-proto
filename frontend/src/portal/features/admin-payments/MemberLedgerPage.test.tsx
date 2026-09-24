import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { MemberLedger } from '@/portal/api/types';
import { makeLedger, makeMandate } from '@test/fixtures/finance';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MemberLedgerPage } from './MemberLedgerPage';

/** Serve one member's ledger. */
function serveLedger(ledger: MemberLedger = makeLedger()) {
  server.use(http.get(`${API}/admin/payments/ledger/37`, () => HttpResponse.json(ledger)));
}

function renderLedger() {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/payments/members/:userId" element={<MemberLedgerPage />} />
    </Routes>,
    { route: '/admin/payments/members/37' },
  );
}

describe('MemberLedgerPage', () => {
  it('names the member the ledger is about', async () => {
    serveLedger();
    renderLedger();

    expect(await screen.findByRole('heading', { name: 'Marta Reyes' })).toBeInTheDocument();
  });

  it('reports what the member has paid over their whole history', async () => {
    serveLedger();
    renderLedger();

    expect(await screen.findByText('$435.00')).toBeInTheDocument();
  });

  it('lists every payment with a link to its record', async () => {
    serveLedger();
    renderLedger();

    const table = await screen.findByRole('table');
    expect(within(table).getByRole('link', { name: 'CALDART-000412' })).toHaveAttribute(
      'href',
      '/admin/payments/412',
    );
  });

  it('says the member renews by hand when they hold no mandate', async () => {
    serveLedger();
    renderLedger();

    expect(await screen.findByText('This member renews by hand.')).toBeInTheDocument();
  });

  it('describes the saved method when the member has a mandate', async () => {
    serveLedger(makeLedger({ mandate: makeMandate() }));
    renderLedger();

    expect(await screen.findByText('Visa ending 4242, expires 03/2028')).toBeInTheDocument();
  });

  it('names why the last automatic charge was refused', async () => {
    serveLedger(
      makeLedger({
        mandate: makeMandate({ status: 'paused', last_error: 'Your card was declined' }),
      }),
    );
    renderLedger();

    expect(await screen.findByText('Your card was declined')).toBeInTheDocument();
  });

  it('offers a statement for each year the member gave in', async () => {
    serveLedger();
    renderLedger();

    expect(await screen.findByRole('link', { name: '2026' })).toHaveAttribute(
      'href',
      '/api/v1/admin/payments/ledger/37/statements/2026.pdf',
    );
  });

  it('says so when the member has given nothing', async () => {
    serveLedger(makeLedger({ statement_years: [] }));
    renderLedger();

    expect(
      await screen.findByText('This member has not given anything beyond their dues.'),
    ).toBeInTheDocument();
  });

  it('explains a ledger it could not load', async () => {
    server.use(
      http.get(`${API}/admin/payments/ledger/37`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderLedger();

    expect(await screen.findByText('That ledger could not be loaded')).toBeInTheDocument();
  });
});
