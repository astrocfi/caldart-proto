/**
 * The Automatic renewal card on the member's Payments screen.
 *
 * It has four faces, one per mandate status, and a fifth for a member who has
 * never turned renewal on.  Every one of them says plainly whether CalDART will
 * charge anything, and what to press to change that.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { RenewalMandate } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { Money, formatCents } from '@/portal/components/Money';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { ContributionForm } from './ContributionForm';
import { RenewalSetup } from './RenewalSetup';
import { useCancelRenewal, useRenewal } from './api';

/** What the card offers to do next; `setup` is the inline turn-on flow. */
type Mode = 'idle' | 'setup' | 'contribution' | 'confirm-off';

/**
 * The member's automatic-renewal state, with the controls that change it.
 *
 * A mandate that is `pending` was started and never finished, so it is offered
 * the same way as no mandate at all: the only useful thing to do with it is to
 * run the setup flow again.
 */
export function AutoRenewalCard(): JSX.Element {
  const renewal = useRenewal();
  const cancel = useCancelRenewal();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>('idle');

  const mandate = renewal.data?.mandate ?? null;
  const isOn = mandate !== null && mandate.status === 'active';

  function handleDone(): void {
    setMode('idle');
    toast.show('Automatic renewal is on.', 'success');
  }

  async function turnOff(): Promise<void> {
    try {
      await cancel.mutateAsync();
      setMode('idle');
      toast.show('Automatic renewal is off.', 'success');
    } catch {
      toast.show('Automatic renewal could not be turned off. Please try again.', 'error');
    }
  }

  return (
    <Card eyebrow="Membership" title="Automatic renewal">
      {renewal.isPending ? (
        <p className="muted" role="status">
          Checking your renewal settings…
        </p>
      ) : (
        <>
          <MandateSummary mandate={mandate} />

          {mode === 'setup' ? (
            <RenewalSetup
              initialContributionCents={mandate?.contribution_cents ?? 0}
              onCancel={() => setMode('idle')}
              onDone={handleDone}
            />
          ) : null}

          {mode === 'contribution' && mandate ? (
            <ContributionForm mandate={mandate} onDone={() => setMode('idle')} />
          ) : null}

          {mode === 'confirm-off' && mandate ? (
            <div className="renewal__confirm stack">
              <p>
                Turn automatic renewal off? Nothing further is charged and your saved method is
                dropped. Your membership still runs to the end of the term you have paid for.
              </p>
              <div className="cluster">
                <Button variant="danger" onClick={() => void turnOff()} disabled={cancel.isPending}>
                  {cancel.isPending ? 'Turning off…' : 'Yes, turn it off'}
                </Button>
                <Button variant="quiet" onClick={() => setMode('idle')}>
                  Keep it on
                </Button>
              </div>
            </div>
          ) : null}

          {mode === 'idle' ? (
            <div className="cluster card__footer">
              {isOn ? (
                <>
                  <Button variant="secondary" onClick={() => setMode('contribution')}>
                    Change contribution
                  </Button>
                  <Button variant="quiet" onClick={() => setMode('confirm-off')}>
                    Turn off
                  </Button>
                </>
              ) : (
                <Button onClick={() => setMode('setup')}>
                  {mandate?.status === 'paused' ? 'Turn on again' : 'Turn on'}
                </Button>
              )}
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}

/** The prose above the buttons: what CalDART will do, and when. */
function MandateSummary({ mandate }: { mandate: RenewalMandate | null }): JSX.Element {
  if (mandate === null || mandate.status === 'pending') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          Your membership does not renew itself. Turn this on and CalDART charges a saved card or
          PayPal account the day before your membership runs out, so it never lapses.
        </p>
      </div>
    );
  }

  if (mandate.status === 'canceled') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          You turned automatic renewal off on <DateText value={mandate.canceled_at} />. Your
          membership runs to the end of the term you have paid for, and the ordinary renewal
          reminders apply again.
        </p>
      </div>
    );
  }

  if (mandate.status === 'paused') {
    return (
      <div className="stack">
        <StatusChip tone="expired" label="Stopped" />
        <p>
          Automatic renewal stopped because CalDART could not charge{' '}
          {mandate.method_label || 'your saved payment method'}.
        </p>
        {mandate.last_error ? (
          <p className="renewal__error">The last attempt was refused: {mandate.last_error}</p>
        ) : null}
        <p>
          Nothing about your current membership has changed. Save another method to start it up
          again, or renew by hand from the Renew screen.
        </p>
      </div>
    );
  }

  return (
    <div className="stack">
      <StatusChip tone="current" label="On" />
      <dl className="renewal__facts">
        <div>
          <dt>Method</dt>
          <dd>{mandate.method_label}</dd>
        </div>
        <div>
          <dt>Plan</dt>
          <dd>{mandate.plan_name}</dd>
        </div>
        <div>
          <dt>Contribution renewed with it</dt>
          <dd>
            <Money cents={mandate.contribution_cents} />
          </dd>
        </div>
        <div>
          <dt>Next charge</dt>
          <dd>
            {mandate.next_charge_on === null ? (
              <span className="muted">Nothing due yet</span>
            ) : (
              <>
                <DateText value={mandate.next_charge_on} /> ·{' '}
                <span className="mono">{formatCents(mandate.amount_cents)}</span>
              </>
            )}
          </dd>
        </div>
      </dl>
      <p className="muted">
        We email you fourteen days before every charge. While this is on you do not get the ordinary
        renewal reminders.
      </p>
    </div>
  );
}
