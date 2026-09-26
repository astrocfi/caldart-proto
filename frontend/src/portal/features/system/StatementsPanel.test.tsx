import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { StatementsPanel, defaultStatementYear, statementsRunSummary } from './StatementsPanel';

const NOW = new Date('2026-06-15T12:00:00Z');

const RESULT = {
  year: 2025,
  sent: 1,
  skipped: 2,
  failed: 0,
  actions: [
    {
      kind: 'contribution_statement',
      member: 'Dana Doe',
      email: 'dana@example.org',
      on: null,
      amount_cents: 5000,
      detail: '',
    },
  ],
};

describe('defaultStatementYear', () => {
  it('offers the calendar year before today', () => {
    expect(defaultStatementYear(new Date('2026-06-15T12:00:00Z'))).toBe(2025);
  });
});

describe('statementsRunSummary', () => {
  it('says what a rehearsal would have done', () => {
    expect(statementsRunSummary(RESULT, true)).toBe('Would send 1, skip 2, and fail 0.');
  });

  it('says what a real run did', () => {
    expect(statementsRunSummary(RESULT, false)).toBe('Sent 1, skipped 2, and failed 0.');
  });
});

describe('StatementsPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('offers last year by default and rehearses on the first press', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/statements/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(RESULT);
      }),
    );
    renderWithProviders(<StatementsPanel />);

    expect(screen.getByLabelText('Year')).toHaveValue(2025);
    expect(screen.getByLabelText('Dry run (send nothing)')).toBeChecked();

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Would send 1, skip 2, and fail 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ year: 2025, dry_run: true }]);
  });

  it('sends the year the box is changed to', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/statements/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ...RESULT, year: 2023 });
      }),
    );
    renderWithProviders(<StatementsPanel />);

    await userEvent.clear(screen.getByLabelText('Year'));
    await userEvent.type(screen.getByLabelText('Year'), '2023');
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Would send 1, skip 2, and fail 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ year: 2023, dry_run: true }]);
  });

  it('lists who the run reached, under a heading naming what it did', async () => {
    server.use(http.post(`${API}/system/statements/run`, () => HttpResponse.json(RESULT)));
    renderWithProviders(<StatementsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByRole('heading', { name: 'What this run would do' }),
    ).toBeInTheDocument();
    const row = screen.getByRole('row', { name: /Dana Doe/ });
    expect(row).toHaveTextContent('Statement');
    expect(row).toHaveTextContent('$50.00');
  });

  it('sends real emails once the dry-run box is cleared', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/statements/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(RESULT);
      }),
    );
    renderWithProviders(<StatementsPanel />);

    await userEvent.click(screen.getByLabelText('Dry run (send nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Sent 1, skipped 2, and failed 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ year: 2025, dry_run: false }]);
    expect(screen.getByRole('heading', { name: 'What this run did' })).toBeInTheDocument();
  });

  it('reports a run the server refused', async () => {
    server.use(
      http.post(`${API}/system/statements/run`, () =>
        HttpResponse.json({ detail: 'The mail server is unreachable' }, { status: 502 }),
      ),
    );
    renderWithProviders(<StatementsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The mail server is unreachable');
  });
});
