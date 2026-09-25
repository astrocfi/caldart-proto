/**
 * The Automatic renewal card on the member's Payments screen.
 *
 * It has four faces, one per mandate status, and a fifth for a member who has
 * never turned renewal on.  Every one of them says plainly whether CalDART will
 * charge anything, and what to press to change that.
 *
 * A life member's membership never runs out, so their card is about their
 * contribution: it is headed `Automatic contribution`, and the words never
 * promise a renewal they will not get.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { useRenewal } from '@/portal/api/queries';
import type { RenewalMandate } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Money, formatCents } from '@/portal/components/Money';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { useMembership } from '@/portal/features/profile/api';
import { RenewalChangeForm } from './RenewalChangeForm';
import { RenewalSetup } from './RenewalSetup';
import { useCancelRenewal } from './api';
import { automaticCardTitle, automaticKindLabel } from './labels';
import { useSetupReturn } from './setupReturn';

/** What the card offers to do next; `setup` is the inline turn-on flow. */
type Mode = 'idle' | 'setup' | 'change' | 'confirm-off';

/**
 * The member's automatic-renewal state, with the controls that change it.
 *
 * A mandate that is `pending` was started and never finished, so it is offered
 * the same way as no mandate at all: the only useful thing to do with it is to
 * run the setup flow again.
 */
export function AutoRenewalCard(): JSX.Element {
  const renewal = useRenewal();
  const membership = useMembership();
  const cancel = useCancelRenewal();
  const setupReturn = useSetupReturn();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>('idle');

  const mandate = renewal.data?.mandate ?? null;
  const isOn = mandate !== null && mandate.status === 'active';
  const isLifetime = membership.data?.is_lifetime ?? false;
  const title = automaticCardTitle(isLifetime);

  function handleDone(): void {
    setMode('idle');
    toast.show(`${title} is on.`, 'success');
  }

  async function turnOff(): Promise<void> {
    try {
      await cancel.mutateAsync();
      setMode('idle');
      toast.show(`${title} is off.`, 'success');
    } catch {
      toast.show(`${title} could not be turned off. Please try again.`, 'error');
    }
  }

  return (
    <Card eyebrow="Membership" title={title}>
      {setupReturn.isConfirming ? (
        <p className="muted" role="status">
          Finishing off the payment method you just saved…
        </p>
      ) : null}
      {setupReturn.error ? (
        <p className="renewal__error" role="alert">
          {setupReturn.error}
        </p>
      ) : null}

      {renewal.isPending ? (
        <p className="muted" role="status">
          Checking your renewal settings…
        </p>
      ) : renewal.error ? (
        // Saying "Off" here would be a statement about the member's money that
        // nothing has established, so the card says only that it does not know.
        <EmptyState
          title="Your renewal settings could not be read"
          description="We cannot tell you whether CalDART renews your membership automatically. Try again, or contact CalDART if it keeps happening."
          action={
            <Button variant="secondary" onClick={() => void renewal.refetch()}>
              Try again
            </Button>
          }
        />
      ) : (
        <>
          <MandateSummary mandate={mandate} isLifetime={isLifetime} />

          {mode === 'setup' ? (
            <RenewalSetup
              isLifetime={isLifetime}
              initialContributionCents={mandate?.contribution_cents ?? 0}
              onCancel={() => setMode('idle')}
              onDone={handleDone}
            />
          ) : null}

          {mode === 'change' && mandate ? (
            <RenewalChangeForm
              mandate={mandate}
              isLifetime={isLifetime}
              onDone={() => setMode('idle')}
            />
          ) : null}

          {mode === 'confirm-off' && mandate ? (
            <div className="renewal__confirm stack">
              <p>
                Turn {title.toLowerCase()} off? Nothing further is charged and your saved method is
                dropped.{' '}
                {isLifetime
                  ? 'Your membership is untouched: it never runs out.'
                  : 'Your membership still runs to the end of the term you have paid for.'}
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
                  <Button variant="secondary" onClick={() => setMode('change')}>
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

interface MandateSummaryProps {
  mandate: RenewalMandate | null;
  isLifetime: boolean;
}

/** The prose above the buttons: what CalDART will do, and when. */
function MandateSummary({ mandate, isLifetime }: MandateSummaryProps): JSX.Element {
  if (mandate === null || mandate.status === 'pending') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          {isLifetime
            ? 'Your contribution is not taken automatically. Turn this on and CalDART will charge a saved card or PayPal account once a year for the contribution you choose.'
            : 'Your membership does not renew itself. Turn this on and CalDART will charge a saved card or PayPal account the day before your membership runs out, so it never lapses.'}
        </p>
      </div>
    );
  }

  const authority = automaticKindLabel(mandate.kind);
  const isContributionOnly = mandate.kind === 'contribution';

  if (mandate.status === 'canceled') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          You turned {authority.toLowerCase()} off on <DateText value={mandate.canceled_at} />.{' '}
          {isContributionOnly
            ? 'Nothing further is taken. You can contribute at any time from the Renew screen.'
            : 'Your membership runs to the end of the term you have paid for, and the ordinary renewal reminders apply again.'}
        </p>
      </div>
    );
  }

  if (mandate.status === 'paused') {
    return (
      <div className="stack">
        <StatusChip tone="expired" label="Stopped" />
        <p>
          {authority} stopped because CalDART could not charge{' '}
          {mandate.method_label || 'your saved payment method'}.
        </p>
        {mandate.last_error ? (
          <p className="renewal__error">The last attempt was refused: {mandate.last_error}</p>
        ) : null}
        <p>
          {isContributionOnly
            ? 'Nothing about your membership has changed. Save another method to start it up again, or contribute by hand from the Renew screen.'
            : 'Nothing about your current membership has changed. Save another method to start it up again, or renew by hand from the Renew screen.'}
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
        {mandate.plan_name === null ? null : (
          <div>
            <dt>Plan</dt>
            <dd>{mandate.plan_name}</dd>
          </div>
        )}
        <div>
          <dt>
            {isContributionOnly ? 'Contribution charged each year' : 'Contribution renewed with it'}
          </dt>
          <dd>
            <Money cents={mandate.contribution_cents} />
          </dd>
        </div>
        <div>
          <dt>Next charge</dt>
          <dd>
            <DateText value={mandate.next_charge_on} /> ·{' '}
            <span className="mono">{formatCents(mandate.amount_cents)}</span>
          </dd>
        </div>
      </dl>
      <p className="muted">
        We will email you fourteen days before every charge.
        {isContributionOnly
          ? null
          : ' While this is on you do not get the ordinary renewal reminders.'}
      </p>
    </div>
  );
}
