/**
 * The checks at the top of **Check and send**: mistakes the server found in the
 * saved email, each with a dot for how much it matters.
 *
 * An error (*Must fix*), such as a Reply-To that is not an address, must be fixed
 * before the email can go; a warning (*Worth a look*), such as a link that does
 * not load, is worth a look but the sender may send anyway. The card runs the
 * checks when it opens and again before the confirmation; **Check again** runs
 * them after a fix. Words the screen could not save are listed first, as mistakes
 * to fix, each with a link that puts the focus in the field. While the card still
 * lists steps before the email can go, a clean result says *Nothing else to fix*
 * rather than that nothing is wrong.
 */
import type { JSX, MouseEvent, RefObject } from 'react';

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

/** Where the compose screen's **What it says** card is, for a link to it. */
export const WHAT_IT_SAYS_ID = 'bulk-email-what-it-says';

/**
 * A mistake that kept the words typed from saving: what to say, and the field it is
 * in, when the server named one.
 */
export interface SaveProblem {
  key: string;
  message: string;
  field?: 'subject' | 'body';
}

interface ChecksListProps {
  /** Lets the card put the focus on **Check again** when a press finds a problem. */
  checkAgainRef?: RefObject<HTMLButtonElement | null>;
  /** The latest findings, or undefined before the checks have answered. */
  findings: BulkEmailFinding[] | undefined;
  isChecking: boolean;
  /** Why the checks could not be run, if they could not. */
  error: unknown;
  onCheckAgain: () => void;
  /** Words the screen could not save, which must be fixed before the email can go. */
  saveProblems?: readonly SaveProblem[];
  /** Puts the focus in a field named by a save problem. */
  onFixField?: (field: 'subject' | 'body') => void;
  /** True while the card still lists steps to take before the email can go. */
  hasMissingSteps?: boolean;
}

/** The checks' findings, a sentence on what they mean, and **Check again**. */
export function ChecksList({
  checkAgainRef,
  findings,
  isChecking,
  error,
  onCheckAgain: handleCheckAgain,
  saveProblems = [],
  onFixField: handleFixField,
  hasMissingSteps = false,
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
      {saveProblems.length === 0 ? null : (
        <ul className="bulk-email__findings" aria-label="Not saved">
          {saveProblems.map((problem) => (
            <li key={problem.key} className="bulk-email__finding" role="alert">
              <span aria-hidden="true">
                <StatusDot tone="expired" label="" />
              </span>
              <span>
                <strong>{LEVEL_WORDS.error}</strong> {problem.message}{' '}
                {problem.field === undefined || handleFixField === undefined ? null : (
                  <FixLink field={problem.field} onFix={handleFixField} />
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Findings
        findings={findings}
        isChecking={isChecking}
        error={error}
        hasMissingSteps={hasMissingSteps || saveProblems.length > 0}
      />
    </section>
  );
}

/** *Fix it under 2. What it says*: a link to the card that puts the focus in `field`. */
function FixLink({
  field,
  onFix: handleFix,
}: {
  field: 'subject' | 'body';
  onFix: (field: 'subject' | 'body') => void;
}): JSX.Element {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>): void => {
    event.preventDefault();
    handleFix(field);
  };
  return (
    <a href={`#${WHAT_IT_SAYS_ID}`} onClick={handleClick}>
      Fix it under 2. What it says.
    </a>
  );
}

interface FindingsProps {
  findings: BulkEmailFinding[] | undefined;
  isChecking: boolean;
  error: unknown;
  hasMissingSteps: boolean;
}

/** The findings, or what stands in for them while they are read or if they cannot be. */
function Findings({ findings, isChecking, error, hasMissingSteps }: FindingsProps): JSX.Element {
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
  if (shown.length === 0 && hasMissingSteps) {
    return (
      <p className="bulk-email__finding" role="status">
        Nothing else to fix.
      </p>
    );
  }
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
