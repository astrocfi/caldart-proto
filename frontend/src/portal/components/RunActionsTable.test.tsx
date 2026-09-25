import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { RunAction } from '@/portal/api/types';
import { actionsHeading, RunActionsTable } from './RunActionsTable';

const ACTIONS: RunAction[] = [
  {
    kind: 'renewal_notice',
    member: 'Dana Lee',
    email: 'dana@example.org',
    on: '2026-06-19',
    amount_cents: null,
    detail: '',
  },
];

describe('actionsHeading', () => {
  it('names a rehearsal', () => {
    expect(actionsHeading(true)).toBe('What a live run would do');
  });

  it('names a real run', () => {
    expect(actionsHeading(false)).toBe('What this run did');
  });
});

describe('RunActionsTable', () => {
  it('reads each row through the caller-supplied kind label', () => {
    render(<RunActionsTable actions={ACTIONS} dryRun={true} kindLabel={() => 'Notice'} />);

    const table = screen.getByRole('table', { name: '1 action' });
    expect(within(table).getByRole('row', { name: /Dana Lee/ })).toHaveTextContent('Notice');
  });

  it("shows each action's detail under the heading the caller names", () => {
    const roster = { ...ACTIONS[0]!, kind: 'roster', detail: 'Bay Area DART' };
    render(
      <RunActionsTable
        actions={[roster]}
        dryRun={true}
        kindLabel={() => 'Roster'}
        detailHeader="DART or report"
      />,
    );

    expect(screen.getByRole('columnheader', { name: 'DART or report' })).toBeInTheDocument();
    expect(screen.getByRole('row', { name: /Dana Lee/ })).toHaveTextContent('Bay Area DART');
  });

  it('leaves the detail out when no heading is named', () => {
    render(<RunActionsTable actions={ACTIONS} dryRun={true} kindLabel={() => 'Notice'} />);

    expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'What',
      'Who',
      'When',
      'Amount',
    ]);
  });

  it('is empty when nothing was due', () => {
    render(<RunActionsTable actions={[]} dryRun={false} kindLabel={(kind) => kind} />);

    expect(screen.getByText('Nothing was due')).toBeInTheDocument();
  });
});
