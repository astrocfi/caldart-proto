/**
 * The cards on the member's Payments screen that state a standing authority.
 *
 * `MandateCard` is one component for both of a person's authorities: the
 * automatic renewal, which renews their membership each year, and the recurring
 * donation, which gives monthly, quarterly, or yearly.  Each has four faces, one
 * per mandate status, and a fifth for somebody who has none.  Every one of them
 * says plainly whether CalDART will charge anything, and what to press to change
 * that.
 *
 * A renewal is turned on in place.  A recurring donation is set up on the Donate
 * screen, where the first gift can be taken at once, so its card links there.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { useMandate } from '@/portal/api/queries';
import type { MandateScope } from '@/portal/api/queries';
import type { IsoDate, RenewalMandate } from '@/portal/api/types';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText, formatDate } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Money, formatCents } from '@/portal/components/Money';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { useMembership } from '@/portal/features/profile/api';
import { RenewalChangeForm } from './RenewalChangeForm';
import { RenewalSetup } from './RenewalSetup';
import { useCancelRenewal } from './api';
import { isAfterExpiry } from './chargeDate';
import { CADENCE_LABELS, automaticKindLabel } from './labels';
import { useSetupReturn } from './setupReturn';

/** What the card offers to do next; `setup` is the renewal's inline turn-on flow. */
type Mode = 'idle' | 'setup' | 'change' | 'confirm-off';

/** Where a recurring donation is set up. */
const DONATE_PATH = '/donate';

/** The eyebrow and heading over each scope's card. */
const CARD_HEADINGS: Record<MandateScope, { eyebrow: string; title: string }> = {
  renewal: { eyebrow: 'Membership', title: 'Automatic renewal' },
  donation: { eyebrow: 'Giving', title: 'Recurring donation' },
};

/** The member's automatic renewal, with the controls that change it. */
export function AutoRenewalCard(): JSX.Element {
  return <MandateCard scope="renewal" />;
}

export interface MandateCardProps {
  scope: MandateScope;
}

/**
 * One standing authority's state, with the controls that change it.
 *
 * A mandate that is `pending` was started and never finished, so it is offered
 * the same way as no mandate at all: the only useful thing to do with it is to
 * set it up again.
 */
export function MandateCard({ scope }: MandateCardProps): JSX.Element {
  const query = useMandate(scope);
  const membership = useMembership();
  const cancel = useCancelRenewal(scope);
  const setupReturn = useSetupReturn(scope);
  const toast = useToast();
  const [mode, setMode] = useState<Mode>('idle');

  const mandate = query.data?.mandate ?? null;
  const isOn = mandate !== null && mandate.status === 'active';
  const isDonation = scope === 'donation';
  const expiresOn = membership.data?.expires_on ?? null;
  const { eyebrow, title } = CARD_HEADINGS[scope];

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
    <Card eyebrow={eyebrow} title={title}>
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

      {query.isPending ? (
        <p className="muted" role="status">
          Checking your {title.toLowerCase()} settings…
        </p>
      ) : query.error ? (
        // Saying "Off" here would be a statement about the member's money that
        // nothing has established, so the card says only that it does not know.
        <EmptyState
          title={`Your ${title.toLowerCase()} settings could not be read`}
          description={`We cannot tell you whether CalDART charges you for a ${title.toLowerCase()}. Try again, or contact CalDART if it keeps happening.`}
          action={
            <Button variant="secondary" onClick={() => void query.refetch()}>
              Try again
            </Button>
          }
        />
      ) : (
        <>
          {isDonation ? (
            <DonationSummary mandate={mandate} />
          ) : (
            <RenewalSummary mandate={mandate} expiresOn={expiresOn} />
          )}

          {/* The setup flow opens on the day the membership runs out, so it waits
              for the membership itself: guessing today would authorize a charge
              that throws away coverage the member has already paid for. */}
          {mode === 'setup' && !isDonation ? (
            membership.isPending ? (
              <p className="muted" role="status">
                Checking when your membership runs out…
              </p>
            ) : membership.isSuccess ? (
              <RenewalSetup
                expiresOn={expiresOn}
                initialContributionCents={mandate?.contribution_cents ?? 0}
                onCancel={() => setMode('idle')}
                onDone={handleDone}
              />
            ) : (
              <EmptyState
                title="Your membership could not be read"
                description="CalDART cannot tell which day your first charge should fall on, so it cannot offer you one yet. Try again, or contact CalDART if it keeps happening."
                action={
                  <Button variant="secondary" onClick={() => void membership.refetch()}>
                    Try again
                  </Button>
                }
              />
            )
          ) : null}

          {mode === 'change' && mandate ? (
            <RenewalChangeForm scope={scope} mandate={mandate} onDone={() => setMode('idle')} />
          ) : null}

          {mode === 'confirm-off' && mandate ? (
            <div className="renewal__confirm stack">
              <p>
                {isDonation
                  ? 'Turn your recurring donation off? Nothing further is charged and your saved method is dropped.'
                  : 'Turn automatic renewal off? Nothing further is charged and your saved method is dropped. Your membership still runs to the end of the term you have paid for.'}
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
                    Change
                  </Button>
                  <Button variant="quiet" onClick={() => setMode('confirm-off')}>
                    Turn off
                  </Button>
                </>
              ) : isDonation ? (
                <ButtonLink to={DONATE_PATH}>Set up</ButtonLink>
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

interface RenewalSummaryProps {
  mandate: RenewalMandate | null;
  /** The day the membership runs out, or null when it never does or there is none. */
  expiresOn: IsoDate | null;
}

/** The prose above an automatic renewal's buttons: what CalDART will do, and when. */
function RenewalSummary({ mandate, expiresOn }: RenewalSummaryProps): JSX.Element {
  if (mandate === null || mandate.status === 'pending') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          Turn this on and CalDART will charge a saved card or PayPal account on the day you choose,
          normally the day your membership runs out, so it never lapses.
        </p>
      </div>
    );
  }

  const authority = automaticKindLabel(mandate.kind);

  if (mandate.status === 'canceled') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          You turned {authority.toLowerCase()} off on <DateText value={mandate.canceled_at} />. Your
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
          {authority} stopped because CalDART could not charge{' '}
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
        {mandate.plan_name === null ? null : (
          <div>
            <dt>Plan</dt>
            <dd>{mandate.plan_name}</dd>
          </div>
        )}
        <div>
          <dt>Contribution renewed with it</dt>
          <dd>
            <Money cents={mandate.contribution_cents} />
          </dd>
        </div>
        <div>
          <dt>Next charge</dt>
          <dd>
            <DateText value={mandate.next_charge_on} />
            {isAfterExpiry(mandate.next_charge_on, expiresOn) ? (
              // The phrase is about the day, so it sits with the day rather than
              // after the amount, where it would read as a clause about money.
              <span className="muted">
                {' '}
                after your membership runs out on {formatDate(expiresOn)}
              </span>
            ) : null}{' '}
            · <span className="mono">{formatCents(mandate.amount_cents)}</span>
          </dd>
        </div>
      </dl>
      <p className="muted">
        We will email you fourteen days before every charge. While this is on you do not get the
        ordinary renewal reminders.
      </p>
    </div>
  );
}

/** The prose above a recurring donation's buttons: what CalDART will take, and when. */
function DonationSummary({ mandate }: { mandate: RenewalMandate | null }): JSX.Element {
  if (mandate === null || mandate.status === 'pending') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          Set one up on the Donate screen and CalDART will charge a saved card or PayPal account
          monthly, quarterly, or yearly, for the amount you choose.
        </p>
      </div>
    );
  }

  if (mandate.status === 'canceled') {
    return (
      <div className="stack">
        <StatusChip tone="none" label="Off" />
        <p>
          You turned your recurring donation off on <DateText value={mandate.canceled_at} />.
          Nothing further is taken. You can give at any time from the Donate screen.
        </p>
      </div>
    );
  }

  if (mandate.status === 'paused') {
    return (
      <div className="stack">
        <StatusChip tone="expired" label="Stopped" />
        <p>
          Your recurring donation stopped because CalDART could not charge{' '}
          {mandate.method_label || 'your saved payment method'}.
        </p>
        {mandate.last_error ? (
          <p className="renewal__error">The last attempt was refused: {mandate.last_error}</p>
        ) : null}
        <p>Set it up again with another method from the Donate screen.</p>
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
          <dt>Amount</dt>
          <dd>
            <Money cents={mandate.contribution_cents} />
          </dd>
        </div>
        <div>
          <dt>How often</dt>
          <dd>{CADENCE_LABELS[mandate.cadence]}</dd>
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
        {mandate.cadence === 'yearly'
          ? 'We will email you fourteen days before every charge.'
          : 'We email you a receipt after every charge.'}
      </p>
    </div>
  );
}
