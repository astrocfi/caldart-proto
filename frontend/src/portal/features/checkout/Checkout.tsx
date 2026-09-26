/**
 * The shared checkout widget used by `/join`, `/renew`, and `/donate`.
 *
 * Choose a plan, optionally add a contribution, then pay with whichever
 * providers this deployment has keys for.  In `contribute` mode there is no
 * plan to choose: the payment buys no membership term, which is the only thing
 * a life member can do here, so one is shown this form whatever mode was asked
 * for.
 *
 * A contribution can be made a recurring donation, monthly, quarterly, or
 * yearly.  With the first charge today it is paid now and the method saved for
 * the charges after it; with a later day nothing is paid now, and the method is
 * saved through the setup flow instead (`onScheduled` reports that).  A member
 * whose automatic renewal already takes a contribution is refused the donation by
 * the server, and the widget then asks, in the server's words, whether to move it:
 * a contribution lives in one place.
 *
 * A finished payment is reported through `onSuccess` and nothing else: the flow
 * that hosts the widget owns the queries a payment moves, so the refresh happens
 * once, where the keys are known.  A host where paying is optional passes
 * `onSkip`, and the widget offers a quiet **Not now** button under the provider
 * tabs that calls it.
 */
import { useEffect, useId, useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { IsoDate, PaymentProvider } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate, todayIso } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { formatCents } from '@/portal/components/Money';
import { MandateSetupTabs } from '@/portal/features/payments/MandateSetupTabs';
import { PROVIDER_ORDER, usePaymentsConfig } from './api';
import { ContributionChooser } from './ContributionChooser';
import { PlanChooser } from './PlanChooser';
import { ProviderTabs } from './ProviderTabs';
import { RecurringDonationFields } from './RecurringDonationFields';
import type { RecurringDonation } from './RecurringDonationFields';
import type { CheckoutMode, CheckoutProps, ProviderPanelProps } from './types';
import './checkout.css';

/** Renewals default to the annual plan. */
const DEFAULT_PLAN = 'annual';

/** The eyebrow and title over each mode's form. */
const HEADINGS: Record<CheckoutMode, { eyebrow: string; title: string }> = {
  join: { eyebrow: 'Membership', title: 'Join CalDART' },
  renew: { eyebrow: 'Renewal', title: 'Renew your membership' },
  contribute: { eyebrow: 'Contribution', title: 'Make a contribution' },
};

export type { CheckoutProps, CheckoutResult } from './types';

/** `CheckoutProps`, plus the way out a host offers where paying is optional. */
export interface SkippableCheckoutProps extends CheckoutProps {
  /** Called by the **Not now** button; the button is shown only when this is given. */
  onSkip?: () => void;
}

/**
 * Choose a plan and a contribution, then pay with the configured providers, or
 * press **Not now** when the host passed `onSkip`.
 */
export function Checkout({
  mode,
  onSuccess,
  onScheduled: handleScheduled,
  onSkip: handleSkip,
}: SkippableCheckoutProps): JSX.Element {
  const { data: config, isPending, error } = usePaymentsConfig();
  const { user } = useAuth();

  const [plan, setPlan] = useState<string>(DEFAULT_PLAN);
  const [contributionCents, setContributionCents] = useState(0);
  const [isOther, setIsOther] = useState(false);
  const [provider, setProvider] = useState<PaymentProvider | null>(null);
  const [autoRenew, setAutoRenew] = useState(false);
  const [recurring, setRecurring] = useState<RecurringDonation>(() => ({
    isRecurring: false,
    cadence: 'monthly',
    firstChargeOn: todayIso(),
  }));
  const [isMoveAgreed, setIsMoveAgreed] = useState(false);
  // The server's sentence when it refused the donation because the member's
  // renewal already takes a contribution; null until it has.
  const [moveMessage, setMoveMessage] = useState<string | null>(null);
  const [scheduledOn, setScheduledOn] = useState<IsoDate | null>(null);
  const autoRenewId = useId();

  const providers = useMemo(
    () => PROVIDER_ORDER.filter((slug) => config?.providers.includes(slug)),
    [config],
  );

  // A life member has nothing left to buy, and the server refuses a plan from
  // them, so every mode collapses to the contribution form.
  const isLifetime = user?.membership.is_lifetime ?? false;
  const effectiveMode: CheckoutMode = isLifetime ? 'contribute' : mode;
  const heading = HEADINGS[effectiveMode];

  useEffect(() => {
    if (provider === null && providers[0]) setProvider(providers[0]);
  }, [providers, provider]);

  if (isPending) {
    return (
      <Card eyebrow={heading.eyebrow} title="Payment">
        <p className="muted" role="status">
          Loading payment options…
        </p>
        <SkipFooter onSkip={handleSkip} />
      </Card>
    );
  }

  if (error || !config) {
    return (
      <Card eyebrow={heading.eyebrow} title="Payment">
        <EmptyState
          title="Payment options could not be loaded"
          description="Please reload the page, or contact CalDART if it keeps happening."
        />
        <SkipFooter onSkip={handleSkip} />
      </Card>
    );
  }

  const isContributing = effectiveMode === 'contribute';

  // "Annual" is only the default where the server offers it; anywhere else the
  // first plan on the list stands in, so the chooser always has a selection.
  const offered = config.plans.map((entry) => entry.slug);
  const effectivePlan = offered.includes(plan) ? plan : (offered[0] ?? plan);

  const selectedPlan = isContributing
    ? null
    : (config.plans.find((entry) => entry.slug === effectivePlan) ?? null);
  const planCents = selectedPlan?.price_cents ?? 0;
  const totalCents = planCents + contributionCents;

  // Only a plan with a term can renew itself, and a contribution can only
  // repeat once there is an amount, so the offer is hidden rather than shown
  // and refused by the server.
  const canAutoRenew = isContributing
    ? contributionCents > 0
    : selectedPlan !== null && selectedPlan.duration_days !== null;

  // The server refuses a payment of nothing, so a contribution waits for an
  // amount rather than starting a provider that cannot be paid.
  const needsContribution = isContributing && contributionCents === 0;

  const isDonating = isContributing && canAutoRenew && recurring.isRecurring;
  const needsChargeDate = isDonating && recurring.firstChargeOn === '';
  const isScheduledLater = isDonating && recurring.firstChargeOn > todayIso();
  // A contribution lives in one place: the server refuses a donation while the
  // renewal takes one, and the member agrees to move it before the request is sent
  // again with that agreement.
  const needsMove = isDonating && moveMessage !== null && !isMoveAgreed;

  const panelProps: ProviderPanelProps = {
    plan: isContributing ? null : effectivePlan,
    contributionCents,
    amountCents: totalCents,
    autoRenew: isContributing ? isDonating : canAutoRenew && autoRenew,
    ...(isDonating
      ? {
          cadence: recurring.cadence,
          removeRenewalContribution: isMoveAgreed,
          onRenewalContribution: setMoveMessage,
        }
      : {}),
    onSuccess,
  };

  function handleSetUp(): void {
    setScheduledOn(recurring.firstChargeOn);
    handleScheduled?.(recurring.firstChargeOn);
  }

  return (
    <Card eyebrow={heading.eyebrow} title={heading.title} className="checkout">
      {isContributing ? null : (
        <PlanChooser
          plans={config.plans}
          value={effectivePlan}
          onChange={(next) => setPlan(next)}
        />
      )}

      <ContributionChooser
        tiers={config.contribution_tiers}
        value={contributionCents}
        maxCents={config.max_contribution_cents}
        onChange={(next) => setContributionCents(next)}
        isOther={isOther}
        // codespell:ignore-next-line onother
        onOther={(next) => {
          setIsOther(next);
          if (next) setContributionCents(0);
        }}
      />

      <dl className="checkout__total">
        {isContributing ? null : (
          <div>
            <dt>{selectedPlan?.name ?? 'Membership'}</dt>
            <dd className="mono">{formatCents(planCents)}</dd>
          </div>
        )}
        {contributionCents > 0 ? (
          <div>
            <dt>Contribution</dt>
            <dd className="mono">{formatCents(contributionCents)}</dd>
          </div>
        ) : null}
        <div className="checkout__total-row">
          <dt>Total today</dt>
          <dd className="mono" data-testid="checkout-total">
            {formatCents(isScheduledLater ? 0 : totalCents)}
          </dd>
        </div>
      </dl>

      {isContributing && canAutoRenew ? (
        <RecurringDonationFields
          value={recurring}
          onChange={(next) => setRecurring(next)}
          amountCents={contributionCents}
        />
      ) : null}

      {!isContributing && canAutoRenew ? (
        <div className="checkout__auto-renew">
          <label className="checkout__auto-renew-label" htmlFor={autoRenewId}>
            <input
              id={autoRenewId}
              type="checkbox"
              checked={autoRenew}
              onChange={(event) => setAutoRenew(event.target.checked)}
            />
            <span>Renew automatically each year</span>
          </label>
          <p className="checkout__fineprint muted">
            We will email you 14 days before charging this card, and you can turn it off at any time
            from Payments.
          </p>
        </div>
      ) : null}

      {needsContribution ? (
        <p className="checkout__blocked muted" role="status">
          Choose a contribution to continue.
        </p>
      ) : scheduledOn !== null ? (
        <p className="checkout__notice" role="status">
          Your recurring donation is set up. The first charge is on {formatDate(scheduledOn)}.
        </p>
      ) : needsMove ? (
        <div className="checkout__notice stack">
          <p>{moveMessage}</p>
          <div className="cluster">
            <Button onClick={() => setIsMoveAgreed(true)}>Continue</Button>
          </div>
        </div>
      ) : needsChargeDate ? (
        <p className="checkout__blocked muted" role="status">
          Choose the day of the first charge.
        </p>
      ) : providers.length === 0 ? (
        <EmptyState
          title="Online payment is not set up yet"
          description="Please contact CalDART to pay by check, or try again later."
        />
      ) : isScheduledLater ? (
        <MandateSetupTabs
          config={config}
          panelProps={{
            scope: 'donation',
            plan: null,
            contributionCents,
            nextChargeOn: recurring.firstChargeOn,
            cadence: recurring.cadence,
            removeRenewalContribution: isMoveAgreed,
            onRenewalContribution: setMoveMessage,
            onDone: handleSetUp,
          }}
        />
      ) : (
        <ProviderTabs
          providers={providers}
          active={provider}
          onChange={(next) => setProvider(next)}
          config={config}
          panelProps={panelProps}
        />
      )}

      <SkipFooter onSkip={handleSkip} />
    </Card>
  );
}

/**
 * The **Not now** button, drawn whether or not the payment options loaded, so a host
 * where paying is optional is never left without a way on.
 */
function SkipFooter({ onSkip }: { onSkip: (() => void) | undefined }) {
  if (onSkip === undefined) return null;
  return (
    <div className="cluster card__footer">
      <Button variant="quiet" onClick={() => onSkip()}>
        Not now
      </Button>
    </div>
  );
}
