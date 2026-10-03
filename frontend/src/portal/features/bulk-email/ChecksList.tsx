/**
 * The checks at the top of **Check and send**: mistakes the server found in the
 * saved email, each with a dot for how much it matters.
 *
 * An error (*Must fix*), such as a Reply-To that is not an address, must be fixed
 * before the email can go; a warning (*Worth a look*), such as a link that does
 * not load, is worth a look but the sender may send anyway. The card runs the
 * checks when it opens and again before the confirmation; **Check again** runs
 * them after a fix.
 */
import type { JSX, RefObject } from 'react';

import type { BulkEmailFinding } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { StatusDot } from '@/portal/components/StatusChip';
import { hasError } from './checksApi';

/**
 * The findings the card's own list of missing steps already says, as the words
 * are typed, so they are not listed twice.
 */
const SAID_BY_THE_STEPS: ReadonlySet<string> = new Set(['no_subject', 'no_body']);

/** The findings the list shows: all but those the missing steps already say. */
export function shownFindings(findings: readonly BulkEmailFinding[]): BulkEmailFinding[] {
  return findings.filter((finding) => !SAID_BY_THE_STEPS.has(finding.code));
}

/** What each level is called beside its dot. */
const LEVEL_WORDS: Record<BulkEmailFinding['level'], string> = {
  error: 'Must fix:',
  warning: 'Worth a look:',
};

interface ChecksListProps {
  /** Lets the card put the focus on **Check again** when a press finds a problem. */
  checkAgainRef?: RefObject<HTMLButtonElement | null>;
  /** The latest findings, or undefined before the checks have answered. */
  findings: BulkEmailFinding[] | undefined;
  isChecking: boolean;
  /** Why the checks could not be run, if they could not. */
  error: unknown;
  onCheckAgain: () => void;
}

/** The checks' findings, a sentence on what they mean, and **Check again**. */
export function ChecksList({
  checkAgainRef,
  findings,
  isChecking,
  error,
  onCheckAgain: handleCheckAgain,
}: ChecksListProps): JSX.Element {
  return (
    <section className="bulk-email__checks stack-tight" aria-label="Checks">
      <div className="cluster bulk-email__checks-bar">
        <h3 className="bulk-email__checks-title">Checks</h3>
        <Button
          ref={checkAgainRef}
          small
          variant="quiet"
          disabled={isChecking}
          onClick={handleCheckAgain}
        >
          {isChecking ? 'Checking…' : 'Check again'}
        </Button>
      </div>
      <Findings findings={findings} isChecking={isChecking} error={error} />
    </section>
  );
}

/** The findings, or what stands in for them while they are read or if they cannot be. */
function Findings({
  findings,
  isChecking,
  error,
}: Omit<ChecksListProps, 'onCheckAgain' | 'checkAgainRef'>): JSX.Element {
  if (error !== null && error !== undefined && !isChecking) {
    return (
      <p className="field__error" role="alert">
        The checks could not run. You can still send.
      </p>
    );
  }
  if (findings === undefined) {
    return (
      <p className="muted" role="status">
        Checking the email for mistakes, such as links that do not work…
      </p>
    );
  }
  const shown = shownFindings(findings);
  if (shown.length === 0) {
    return (
      <p className="bulk-email__finding" role="status">
        <StatusDot tone="current" label="Passed" />
        No problems found.
      </p>
    );
  }
  const isBlocked = hasError(shown);
  return (
    <div className="stack-tight" role="status">
      <ul className="bulk-email__findings">
        {shown.map((finding) => (
          <li key={`${finding.code}:${finding.message}`} className="bulk-email__finding">
            {/* The level is written out beside the dot, so the dot's own name is not read too. */}
            <span aria-hidden="true">
              <StatusDot tone={finding.level === 'error' ? 'expired' : 'expiring'} label="" />
            </span>
            <span>
              <strong>{LEVEL_WORDS[finding.level]}</strong> {finding.message}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted">
        {isBlocked
          ? 'Fix each problem marked Must fix, then press Check again before you send.'
          : 'You can still send.'}
      </p>
    </div>
  );
}
