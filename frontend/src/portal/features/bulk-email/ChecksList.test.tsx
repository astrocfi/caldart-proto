import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import type { BulkEmailFinding } from '@/portal/api/types';
import { ChecksList, shownFindings } from './ChecksList';

const WARNING: BulkEmailFinding = {
  code: 'link_broken',
  level: 'warning',
  message: 'This link does not load (the site answered 404): https://example.org/gone',
};

const ERROR: BulkEmailFinding = {
  code: 'reply_to',
  level: 'error',
  message: 'Replies would go to ops, which is not a valid email address.',
};

const NO_SUBJECT: BulkEmailFinding = {
  code: 'no_subject',
  level: 'error',
  message: 'Write a subject.',
};

/** Render the list with `findings`, as the Check and send card would. */
function renderList(findings: BulkEmailFinding[] | undefined, error: unknown = null) {
  const handleCheckAgain = vi.fn();
  renderWithProviders(
    <ChecksList
      findings={findings}
      isChecking={false}
      error={error}
      onCheckAgain={handleCheckAgain}
    />,
  );
  return handleCheckAgain;
}

describe('shownFindings', () => {
  it('leaves out what the missing steps already say', () => {
    expect(shownFindings([NO_SUBJECT, WARNING])).toEqual([WARNING]);
  });
});

describe('ChecksList', () => {
  it('says so while the checks are running', () => {
    renderList(undefined);
    expect(screen.getByRole('status')).toHaveTextContent('Checking the email for mistakes');
  });

  it('says nothing was found', () => {
    renderList([]);
    expect(screen.getByRole('status')).toHaveTextContent('No problems found.');
  });

  it('marks a warning as worth a look, and says the email can still go', () => {
    renderList([WARNING]);
    expect(screen.getByRole('status')).toHaveTextContent(
      `Worth a look: ${WARNING.message}You can still send.`,
    );
  });

  it('marks an error as one to fix before sending', () => {
    renderList([WARNING, ERROR]);
    expect(screen.getByRole('status')).toHaveTextContent(
      'Fix each problem marked Must fix, then press Check again before you send.',
    );
  });

  it('writes each level in words beside its dot', () => {
    renderList([ERROR]);
    expect(screen.getByRole('listitem')).toHaveTextContent(`Must fix: ${ERROR.message}`);
  });

  it('says when the checks could not run, and that the email can still go', () => {
    renderList(undefined, new Error('network'));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The checks could not run. You can still send.',
    );
  });

  it('runs the checks again on Check again', async () => {
    const handleCheckAgain = renderList([WARNING]);
    await userEvent.click(screen.getByRole('button', { name: 'Check again' }));
    expect(handleCheckAgain).toHaveBeenCalledTimes(1);
  });
});
