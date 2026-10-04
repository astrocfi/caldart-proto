/**
 * **Send me a test**, at the bottom of the compose screen's **What it says** card:
 * mails the email to the sender alone, so they can see it in their own mail
 * program as the people in the batch will.
 *
 * The words on the screen are saved first, so the test is the email as written.
 * Every press sends one more test, and each says where it went: *A test went to
 * pat@example.org.* An email with an error the checks catch, such as a missing
 * subject, is not sent, and the errors are listed instead. The focus moves to the
 * line saying what became of the press, since the button was off while it worked.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { Button } from '@/portal/components/Button';
import { refusedFindings, useSendTest } from './checksApi';

/** What the button says when the latest words could not be saved first. */
const NOT_SAVED_MESSAGE =
  'Your latest changes could not be saved, so no test was sent. Try again in a moment.';

/** What the button says when the test fails without a message of its own. */
const FALLBACK_ERROR = 'The test could not be sent. Try again in a minute.';

interface TestSendButtonProps {
  emailId: number;
  /** Save what is typed first; resolves true once it is saved. */
  onBeforeSend: () => Promise<boolean>;
}

/** The button, a line on what it does, and what became of the last press. */
export function TestSendButton({
  emailId,
  onBeforeSend: handleBeforeSend,
}: TestSendButtonProps): JSX.Element {
  const test = useSendTest(emailId);
  const [isUnsaved, setIsUnsaved] = useState(false);
  const outcomeRef = useRef<HTMLDivElement>(null);
  const isSettled = test.isSuccess || test.isError || isUnsaved;

  useEffect(() => {
    if (isSettled) outcomeRef.current?.focus();
  }, [isSettled, test.submittedAt]);

  const handleClick = async (): Promise<void> => {
    setIsUnsaved(false);
    test.reset();
    const isSaved = await handleBeforeSend();
    if (!isSaved) {
      setIsUnsaved(true);
      return;
    }
    test.mutate();
  };

  return (
    <div className="stack-tight bulk-email__test">
      <div className="cluster">
        <Button variant="secondary" disabled={test.isPending} onClick={() => void handleClick()}>
          {test.isPending ? 'Sending a test…' : 'Send me a test'}
        </Button>
      </div>
      <p className="muted bulk-email__test-hint">
        Sends this email to you alone, so you can see it in your own mail program first.
      </p>
      <div ref={outcomeRef} tabIndex={-1} className="stack-tight bulk-email__test-outcome">
        {test.data === undefined ? null : <p role="status">{`A test went to ${test.data.to}.`}</p>}
        {isUnsaved ? (
          <p className="field__error" role="alert">
            {NOT_SAVED_MESSAGE}
          </p>
        ) : null}
        <TestError error={test.error} />
      </div>
    </div>
  );
}

/** Why the test did not go: the checks' errors one per line, or the server's sentence. */
function TestError({ error }: { error: unknown }): JSX.Element | null {
  if (error === null || error === undefined) return null;
  const findings = refusedFindings(error);
  if (findings !== null) {
    return (
      <div className="field__error" role="alert">
        <p>No test was sent. Fix these first:</p>
        <ul>
          {findings.map((finding) => (
            <li key={`${finding.code}:${finding.message}`}>{finding.message}</li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <p className="field__error" role="alert">
      {error instanceof ApiError ? error.message : FALLBACK_ERROR}
    </p>
  );
}
