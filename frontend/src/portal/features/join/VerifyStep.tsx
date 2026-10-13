/** Step 2 — prove the address by following the link we mailed to it. */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { pendingEmailNotice } from '@/portal/auth/pendingEmail';
import { useMe } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ResendVerificationButton } from '@/portal/components/ResendVerificationButton';
import './join.css';

const NOT_YET = 'Not verified yet. Open the link in the message we sent, then try again.';

export interface VerifyStepProps {
  onDone: () => void;
}

/**
 * Step 2 of the join wizard: wait for the visitor to click the verification link.
 *
 * The link opens `/verify-email` in whatever tab the mail client picks, so this step
 * cannot see it being followed; "I've clicked the link" asks `/auth/me` again and
 * moves on only once the server says the address is verified.  While a change of
 * address waits, the link went to the new address, and the step says so.
 */
export function VerifyStep({ onDone: handleDone }: VerifyStepProps): JSX.Element {
  const me = useMe();
  const [notice, setNotice] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const email = me.data?.email ?? '';
  const pending = me.data ? pendingEmailNotice(me.data) : null;

  async function handleCheck() {
    setIsChecking(true);
    const result = await me.refetch();
    setIsChecking(false);
    if (result.data?.email_verified === true) {
      handleDone();
      return;
    }
    setNotice(NOT_YET);
  }

  return (
    <Card className="join-card" title="Check your email">
      {pending !== null ? (
        <p>{pending}</p>
      ) : (
        <p>
          We sent a verification message to {email}. Click the link in it to continue setting up
          your account.
        </p>
      )}
      {notice !== null ? (
        <p className="field__error" role="alert">
          {notice}
        </p>
      ) : null}
      <div className="cluster card__footer">
        <Button onClick={() => void handleCheck()} disabled={isChecking}>
          I&apos;ve clicked the link
        </Button>
        <ResendVerificationButton />
        <Link to="/change-email?next=/join">Use a different email address</Link>
      </div>
    </Card>
  );
}
