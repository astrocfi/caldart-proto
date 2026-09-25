import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ReportRunResult } from '@/portal/api/types';
import { ReportRunOutcome } from './ReportRunOutcome';

function result(overrides: Partial<ReportRunResult> = {}): ReportRunResult {
  return { sent: 2, skipped: 0, failed: 0, skipped_by_reason: {}, actions: [], ...overrides };
}

describe('ReportRunOutcome', () => {
  it('names the counts under the heading naming a rehearsal', () => {
    render(<ReportRunOutcome result={result()} dryRun={true} />);

    expect(screen.getByRole('heading', { name: 'What this run would do' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Would send 2 emails, skipped 0.');
  });

  it('names the counts under the heading naming a real run', () => {
    render(<ReportRunOutcome result={result({ sent: 1 })} dryRun={false} />);

    expect(screen.getByRole('heading', { name: 'What this run did' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Sent 1 email, skipped 0.');
  });

  it('breaks the skip count down by reason', () => {
    render(
      <ReportRunOutcome
        result={result({ skipped: 3, skipped_by_reason: { no_recipients: 2, no_email: 1 } })}
        dryRun={true}
      />,
    );

    expect(screen.getByText('Skipped: nobody ticked 2, no address on file 1.')).toBeInTheDocument();
  });

  it('reports the failed count only when it is above zero', () => {
    render(<ReportRunOutcome result={result({ failed: 0 })} dryRun={true} />);

    expect(screen.queryByText(/^Failed/)).not.toBeInTheDocument();
  });

  it('names each report and roster in the actions table', () => {
    render(
      <ReportRunOutcome
        result={result({
          actions: [
            {
              kind: 'report',
              member: 'Ada Admin',
              email: 'ada@example.org',
              on: null,
              amount_cents: null,
              detail: 'Members, PDF',
            },
          ],
        })}
        dryRun={true}
      />,
    );

    const table = screen.getByRole('table', { name: '1 action' });
    expect(within(table).getByRole('columnheader', { name: 'Report or DART' })).toBeInTheDocument();
    expect(within(table).getByRole('row', { name: /Ada Admin/ })).toHaveTextContent('Members, PDF');
  });

  it('renders the heading before the summary and the summary before the table', () => {
    render(
      <ReportRunOutcome
        result={result({
          actions: [
            {
              kind: 'report',
              member: 'Ada Admin',
              email: 'ada@example.org',
              on: null,
              amount_cents: null,
              detail: 'Members, PDF',
            },
          ],
        })}
        dryRun={true}
      />,
    );

    const heading = screen.getByRole('heading', { name: 'What this run would do' });
    const summary = screen.getByRole('status');
    const table = screen.getByRole('table');

    expect(
      heading.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(summary.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
