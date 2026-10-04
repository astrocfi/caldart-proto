import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { JobPanel, NothingDue, RunNowButton } from './JobPanel';

/** A panel whose run ends as soon as it starts, showing `result` once it has. */
function Harness({ result }: { result: JSX.Element }): JSX.Element {
  const [isRunning, setIsRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const handleRun = (): void => {
    setIsRunning(true);
    setTimeout(() => {
      setIsRunning(false);
      setHasRun(true);
    }, 0);
  };
  return (
    <JobPanel
      eyebrow="Email"
      title="Example job"
      description="The example job runs every morning at 6:00 AM."
      options={
        <label>
          <input type="checkbox" /> Practice run
        </label>
      }
      action={<RunNowButton task="example job" isRunning={isRunning} onClick={handleRun} />}
      isRunning={isRunning}
      result={hasRun ? result : null}
    >
      <h3>The log</h3>
    </JobPanel>
  );
}

const RESULT = (
  <div>
    <h3>What this run did</h3>
    <p>Sent 2 emails.</p>
  </div>
);

/** Whether `elements` stand in the page in the order given. */
function inPageOrder(elements: Element[]): boolean {
  return elements.every(
    (element, index) =>
      index === 0 ||
      (elements[index - 1]!.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING) !==
        0,
  );
}

describe('JobPanel', () => {
  it('puts the description, the options, Run now, the result, and then the rest in that order', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness result={RESULT} />);
    await user.click(screen.getByRole('button', { name: 'Run now: example job' }));
    await screen.findByText('Sent 2 emails.');

    expect(
      inPageOrder([
        screen.getByText('The example job runs every morning at 6:00 AM.'),
        screen.getByLabelText('Practice run'),
        screen.getByRole('button', { name: 'Run now: example job' }),
        screen.getByRole('heading', { name: 'What this run did' }),
        screen.getByRole('heading', { name: 'The log' }),
      ]),
    ).toBe(true);
  });

  it('moves the focus to the result heading once a run ends', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness result={RESULT} />);
    await user.click(screen.getByRole('button', { name: 'Run now: example job' }));

    expect(await screen.findByRole('heading', { name: 'What this run did' })).toHaveFocus();
  });

  it('moves the focus to a failure when the run ends in one', async () => {
    const user = userEvent.setup();
    const failure = <p role="alert">The run failed.</p>;
    renderWithProviders(<Harness result={failure} />);
    await user.click(screen.getByRole('button', { name: 'Run now: example job' }));

    expect(await screen.findByRole('alert')).toHaveFocus();
  });
});

describe('RunNowButton', () => {
  it('reads Running… and holds back while its job runs', () => {
    renderWithProviders(<RunNowButton task="example job" isRunning onClick={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled();
  });
});

describe('NothingDue', () => {
  it.each([
    [true, 'What this run would do', 'Nothing is due.'],
    [false, 'What this run did', 'Nothing was due.'],
  ])('says only that nothing was due (practice run %s)', (dryRun, heading, words) => {
    renderWithProviders(<NothingDue dryRun={dryRun} />);
    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(words);
  });
});
