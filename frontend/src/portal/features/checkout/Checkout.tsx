/**
 * The shared checkout widget used by `/join`, `/renew`, and `/donate`.
 *
 * Choose a plan, optionally add a contribution, then pay with whichever
 * providers this deployment has keys for.  The first plan `GET /payments/config`
 * lists is chosen until somebody picks another; where the server lists none, the
 * form says no membership plan is set up and offers no way to pay for one.  In
 * `contribute` mode there is no
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
 * once, where the keys are known.
 *
 * The widget draws no card, eyebrow, or title of its own: every host already puts it
 * under a heading that says what is being paid for, inside a card of its own.  A
 * donation (`contribute` mode) offers no "No thank you" and starts with no amount
 * chosen, since giving is the point of the form; dues offer it, preselected, since a
 * contribution on top of them is an extra.
 *
 * A host where giving is optional passes `onSkip`: the widget then offers **Continue
 * without a gift**, the main button while no amount is chosen and a quiet one under the
 * payment methods once one is.
 *
 * A host joining somebody as a member may pass `onBecomeFriend`: in `join` mode the
 * plans are then followed by a link-styled **Join as a friend instead (no dues)**
 * button that calls it.  A host offering a friend's donation may pass `onBecomeMember`:
 * in `contribute` mode the amounts are then followed by a link-styled **I changed my
 * mind, I want to be a member** button that calls it.  Neither sends anything to the
 * server; the host decides what the change means.  A life member is offered neither.
 */
import { useEffect, useId, useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { IsoDate, PaymentProvider } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { formatDate, todayIso } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { formatCents } from '@/portal/components/Money';
import { MandateSetupTabs } from '@/portal/features/payments/MandateSetupTabs';
import { PROVIDER_ORDER, usePaymentsConfig } from './api';
import { ContributionChooser, DONATION_HINT } from './ContributionChooser';
import { PlanChooser } from './PlanChooser';
import { ProviderTabs } from './ProviderTabs';
import { RecurringDonationFields } from './RecurringDonationFields';
import type { RecurringDonation } from './RecurringDonationFields';
import type { CheckoutMode, CheckoutProps, ProviderPanelProps } from './types';
import './checkout.css';

export type { CheckoutProps, CheckoutResult } from './types';

/** `CheckoutProps`, plus the way out a host offers where paying is optional. */
export interface SkippableCheckoutProps extends CheckoutProps {
  /**
   * Called by the **Continue without a gift** button; the button is shown only when
   * this is given.
   */
  onSkip?: () => void;
  /** True while the host's skip is in flight: the button waits, so one press is one skip. */
  isSkipping?: boolean;
  /**
   * Called by the **Join as a friend instead (no dues)** button; the button is offered
   * only in `join` mode, never to a life member, and only when this is given.
   */
  onBecomeFriend?: () => void;
  /**
   * Called by the **I changed my mind, I want to be a member** button; the button is
   * offered only in `contribute` mode, never to a life member, and only when this is
   * given.
   */
  onBecomeMember?: () => void;
}

/**
 * Choose a plan and a contribution, then pay with the configured providers, or
 * press **Continue without a gift** when the host passed `onSkip`.
 */
export function Checkout({
  mode,
  onSuccess,
  onScheduled: handleScheduled,
  defaultAutoRenew = false,
  onSkip: handleSkip,
  isSkipping = false,
  onBecomeFriend: handleBecomeFriend,
  onBecomeMember: handleBecomeMember,
}: SkippableCheckoutProps): JSX.Element {
  const { data: config, isPending, error } = usePaymentsConfig();
  const { user } = useAuth();

  // Null until somebody picks: the first plan the server lists stands in for it.
  const [plan, setPlan] = useState<string | null>(null);
  const [contributionCents, setContributionCents] = useState(0);
  const [isOther, setIsOther] = useState(false);
  const [provider, setProvider] = useState<PaymentProvider | null>(null);
  const [autoRenew, setAutoRenew] = useState(defaultAutoRenew);
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

  useEffect(() => {
    if (provider === null && providers[0]) setProvider(providers[0]);
  }, [providers, provider]);

  if (isPending) {
    return (
      <div className="checkout">
        <p className="muted" role="status">
          Loading payment options…
        </p>
        <SkipFooter onSkip={handleSkip} isLead isPending={isSkipping} />
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="checkout">
        <EmptyState
          title="Payment options didn't load"
          description="Reload the page, or contact CalDART if it keeps happening."
        />
        <SkipFooter onSkip={handleSkip} isLead isPending={isSkipping} />
      </div>
    );
  }

  const isContributing = effectiveMode === 'contribute';
  const offersFriend = effectiveMode === 'join' && handleBecomeFriend !== undefined;
  const offersMember = isContributing && !isLifetime && handleBecomeMember !== undefined;
  const friendSwitch = offersFriend ? (
    <SwitchLink onClick={() => handleBecomeFriend?.()}>
      Join as a friend instead (no dues)
    </SwitchLink>
  ) : null;

  // The first plan the server lists stands in until somebody picks one, so the
  // chooser always has a selection whenever there is a plan to select.
  const offered = config.plans.map((entry) => entry.slug);
  const effectivePlan = plan !== null && offered.includes(plan) ? plan : (offered[0] ?? null);

  // A server with no plan set up has nothing to sell a member; becoming a friend
  // and a donation still work without one.
  if (!isContributing && effectivePlan === null) {
    return (
      <div className="checkout">
        <EmptyState
          title="Membership is not on offer yet"
          description="No membership plan is set up yet. Ask an administrator."
        />
        {friendSwitch}
        <SkipFooter onSkip={handleSkip} isLead isPending={isSkipping} />
      </div>
    );
  }

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
    <div className="checkout">
      {isContributing ? null : (
        <PlanChooser
          plans={config.plans}
          value={effectivePlan ?? ''}
          onChange={(next) => setPlan(next)}
        />
      )}
      {friendSwitch}

      <ContributionChooser
        tiers={config.contribution_tiers}
        value={contributionCents}
        maxCents={config.max_contribution_cents}
        onChange={(next) => setContributionCents(next)}
        // A donation stands on its own: there are no dues to add it to, and giving is
        // the point, so nothing is preselected and "No thank you" is not offered.
        legend={isContributing ? 'Your donation' : 'Add a contribution'}
        amountLabel={isContributing ? 'Donation amount' : undefined}
        hint={isContributing ? DONATION_HINT : undefined}
        offerNone={!isContributing}
        isOther={isOther}
        // codespell:ignore-next-line onother
        onOther={(next) => {
          setIsOther(next);
          if (next) setContributionCents(0);
        }}
      />

      {offersMember ? (
        <SwitchLink onClick={() => handleBecomeMember?.()}>
          I changed my mind, I want to be a member
        </SwitchLink>
      ) : null}

      <dl className="checkout__total">
        {isContributing ? null : (
          <div>
            <dt>{selectedPlan?.name ?? 'Membership'}</dt>
            <dd className="num">{formatCents(planCents)}</dd>
          </div>
        )}
        {contributionCents > 0 ? (
          <div>
            <dt>{isContributing ? 'Donation' : 'Contribution'}</dt>
            <dd className="num">{formatCents(contributionCents)}</dd>
          </div>
        ) : null}
        <div className="checkout__total-row">
          <dt>Total today</dt>
          <dd className="num" data-testid="checkout-total">
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
            We will email you 14 days before each charge to your card or PayPal account, and you can
            turn it off at any time from Payments.
          </p>
        </div>
      ) : null}

      {needsContribution ? (
        // Where giving is optional, the button below says what to do instead.
        handleSkip === undefined ? (
          <p className="checkout__blocked muted" role="status">
            Choose a donation amount to continue.
          </p>
        ) : null
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
          description="Contact CalDART to pay by check, or try again later."
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

      <SkipFooter onSkip={handleSkip} isLead={contributionCents === 0} isPending={isSkipping} />
    </div>
  );
}

interface SkipFooterProps {
  onSkip: (() => void) | undefined;
  /** True while nothing is chosen to pay, when the button is the way on. */
  isLead: boolean;
  /** True while the skip is in flight, when the button is disabled. */
  isPending: boolean;
}

/**
 * The **Continue without a gift** button, drawn whether or not the payment options
 * loaded, so a host where giving is optional is never left without a way on.  It is the
 * main button while there is nothing to pay, and a quiet one under the payment methods
 * once there is.
 */
function SkipFooter({ onSkip, isLead, isPending }: SkipFooterProps): JSX.Element | null {
  if (onSkip === undefined) return null;
  return (
    <div className="cluster card__footer">
      <Button variant={isLead ? 'primary' : 'quiet'} disabled={isPending} onClick={() => onSkip()}>
        Continue without a gift
      </Button>
    </div>
  );
}

/**
 * A change of mind between a member's dues and a friend's donation: a button, since it
 * changes the form rather than going anywhere, drawn as a quiet link under the choices.
 */
function SwitchLink({
  onClick: handleClick,
  children,
}: {
  onClick: () => void;
  children: string;
}): JSX.Element {
  return (
    <p className="checkout__switch">
      <button type="button" className="checkout__switch-button" onClick={handleClick}>
        {children}
      </button>
    </p>
  );
}
