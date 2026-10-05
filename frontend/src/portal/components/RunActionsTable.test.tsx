import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { RunAction } from '@/portal/api/types';
import { actionsHeading, RunActionsTable, runActionColumns } from './RunActionsTable';
import { fitColumns } from './tableFit';

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
    expect(actionsHeading(true)).toBe('What this run would do');
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

  it('wraps the heading and the table in a spaced block the caller can space from what came before', () => {
    const { container } = render(
      <RunActionsTable actions={ACTIONS} dryRun={false} kindLabel={() => 'Notice'} />,
    );

    const wrapper = container.querySelector('.run-actions');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('stack-tight');
  });

  it('renders the heading first, then the summary, then the table', () => {
    render(
      <RunActionsTable
        actions={ACTIONS}
        dryRun={false}
        kindLabel={() => 'Notice'}
        summary={<p role="status">Sent 1 email, skipped 0.</p>}
      />,
    );

    const heading = screen.getByRole('heading', { name: 'What this run did' });
    const summary = screen.getByRole('status');
    const table = screen.getByRole('table');

    expect(
      heading.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(summary.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('renders no summary content when the caller passes none', () => {
    render(<RunActionsTable actions={ACTIONS} dryRun={false} kindLabel={() => 'Notice'} />);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
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

  it('keeps the detail, such as the DART or the report, in sight on a narrow screen', () => {
    const roster = { ...ACTIONS[0]!, kind: 'roster', detail: 'Bay Area DART' };
    render(
      <RunActionsTable
        actions={[roster]}
        dryRun={true}
        kindLabel={() => 'Roster'}
        detailHeader="DART or report"
      />,
    );

    expect(screen.getByRole('columnheader', { name: 'DART or report' })).toHaveClass(
      'data-table__wrap',
    );
  });

  it('pins who an action reached while the table scrolls', () => {
    render(<RunActionsTable actions={ACTIONS} dryRun={true} kindLabel={() => 'Notice'} />);

    expect(screen.getByRole('columnheader', { name: 'Who' })).toHaveClass('data-table__identity');
  });

  it('leaves the detail out when no heading is named', () => {
    render(
      <RunActionsTable
        actions={[{ ...ACTIONS[0]!, amount_cents: 4_500, detail: 'Annual' }]}
        dryRun={true}
        kindLabel={() => 'Notice'}
      />,
    );

    expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Who',
      'What',
      'When',
      'Amount',
    ]);
  });

  it('is empty when nothing was due', () => {
    render(<RunActionsTable actions={[]} dryRun={false} kindLabel={(kind) => kind} />);

    expect(screen.getByText('Nothing was due')).toBeInTheDocument();
  });

  it('heads a When and an Amount column for actions that carry them', () => {
    render(
      <RunActionsTable
        actions={[{ ...ACTIONS[0]!, amount_cents: 4_500 }]}
        dryRun={true}
        kindLabel={() => 'Notice'}
      />,
    );

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent);
    expect(headers).toEqual(['Who', 'What', 'When', 'Amount']);
  });

  it('leaves out a column that is empty in every row', () => {
    render(<RunActionsTable actions={ACTIONS} dryRun={true} kindLabel={() => 'Notice'} />);

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent);
    expect(headers).toEqual(['Who', 'What', 'When']);
  });

  it('leaves out When, Amount, and the detail when no row carries them, as for rosters', () => {
    render(
      <RunActionsTable
        actions={[{ ...ACTIONS[0]!, on: null, detail: '' }]}
        dryRun={true}
        kindLabel={() => 'Roster'}
        detailHeader="Report or DART"
      />,
    );

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent);
    expect(headers).toEqual(['Who', 'What']);
  });

  it('leaves the When and Amount columns out for actions that carry neither', () => {
    render(
      <RunActionsTable
        actions={[{ ...ACTIONS[0]!, detail: 'Duplicate address' }]}
        dryRun={true}
        kindLabel={() => 'Sent'}
        detailHeader="Reason"
        hasWhenAndAmount={false}
      />,
    );

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent);
    expect(headers).toEqual(['Who', 'What', 'Reason']);
  });

  it('keeps two actions apart that differ only by the person', () => {
    const twins: RunAction[] = [
      { ...ACTIONS[0]!, member: 'Dana Lee', detail: 'Duplicate address' },
      { ...ACTIONS[0]!, member: 'Dan Lee', detail: 'Duplicate address' },
    ];
    render(<RunActionsTable actions={twins} dryRun={true} kindLabel={() => 'Skipped'} />);

    expect(screen.getByRole('table', { name: '2 actions' })).toHaveTextContent('Dan Lee');
  });

  it('takes a heading of the caller’s own', () => {
    render(
      <RunActionsTable
        actions={ACTIONS}
        dryRun={true}
        kindLabel={() => 'To send'}
        heading="Who this email would reach"
      />,
    );

    expect(screen.getByRole('heading')).toHaveTextContent('Who this email would reach');
  });

  it('takes a caption of the caller’s own', () => {
    render(
      <RunActionsTable
        actions={ACTIONS}
        dryRun={true}
        kindLabel={(kind) => kind}
        caption="1 person"
      />,
    );

    expect(screen.getByRole('table', { name: '1 person' })).toBeInTheDocument();
  });

  it('takes an empty state of the caller’s own', () => {
    render(
      <RunActionsTable
        actions={[]}
        dryRun={true}
        kindLabel={(kind) => kind}
        emptyTitle="Nobody matches these filters"
      />,
    );

    expect(screen.getByText('Nobody matches these filters')).toBeInTheDocument();
  });
});

describe('runActionColumns on a phone', () => {
  /** The room a phone leaves a table inside a Scheduled panel, in rem. */
  const PHONE_REM = 20;

  it('keeps What beside Who, so a practice run says which reminder goes to whom', () => {
    const columns = runActionColumns({ actions: ACTIONS, kindLabel: (kind) => kind });

    expect(fitColumns(columns, PHONE_REM).map((column) => column.key)).toEqual(['member', 'kind']);
  });

  it('gives up When before Amount when the room runs short', () => {
    const charged: RunAction[] = [{ ...ACTIONS[0]!, amount_cents: 4500 }];
    const columns = runActionColumns({ actions: charged, kindLabel: (kind) => kind });

    expect(fitColumns(columns, 32).map((column) => column.key)).toEqual([
      'member',
      'kind',
      'amount_cents',
    ]);
  });
});
