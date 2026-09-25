/**
 * The inline flow that turns automatic renewal on without paying anything.
 *
 * The member picks the plan that will renew, the contribution to renew beside
 * it, and the provider that will hold the method.  Only plans with a duration
 * are offered: a membership for life has nothing to renew.
 *
 * A life member chooses a contribution alone, and must choose one: an authority
 * with nothing to charge is refused by the server, so the provider step waits
 * until there is an amount.
 *
 * The day of the first charge is the member's own.  It opens on the day their
 * membership runs out, which is the day the charge is wanted on, and it may be
 * moved to any later day.
 */
import { useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { IsoDate, MandateProvider } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { formatDate } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import { usePaymentsConfig } from '@/portal/features/checkout/api';
import { ContributionChooser } from '@/portal/features/checkout/ContributionChooser';
import { PlanChooser } from '@/portal/features/checkout/PlanChooser';
import { defaultChargeDate, todayIso } from './chargeDate';
import { MockRenewalPanel } from './MockRenewalPanel';
import { PayPalRenewalPanel } from './PayPalRenewalPanel';
import { StripeRenewalPanel } from './StripeRenewalPanel';
import { MANDATE_PROVIDER_LABELS, MANDATE_PROVIDER_ORDER } from './types';
import '@/portal/features/checkout/checkout.css';

/** The plan a renewal defaults to, where the deployment offers it. */
const DEFAULT_PLAN = 'annual';

export interface RenewalSetupProps {
  /** True for a life member: no plan is offered, and the contribution stands alone. */
  isLifetime?: boolean;
  /**
   * The day the membership runs out, which the first charge opens on.
   *
   * Null for a life member, whose membership never runs out, and for a member
   * with no term at all; both open on a day the server will accept instead.
   */
  expiresOn?: IsoDate | null;
  /** Abandon the flow and go back to the card as it was. */
  onCancel: () => void;
  /** The mandate is active. */
  onDone: () => void;
  /** Prefill the contribution from the authority being replaced. */
  initialContributionCents?: number;
}

/** Plan, contribution and provider, then the chosen provider's own panel. */
export function RenewalSetup({
  onCancel: handleCancel,
  onDone: handleDone,
  isLifetime = false,
  expiresOn = null,
  initialContributionCents = 0,
}: RenewalSetupProps): JSX.Element {
  const { data: config, isPending, error } = usePaymentsConfig();

  const earliestChargeOn = todayIso();
  const [plan, setPlan] = useState<string>(DEFAULT_PLAN);
  const [nextChargeOn, setNextChargeOn] = useState(() =>
    defaultChargeDate({ isLifetime, expiresOn }),
  );
  const [contributionCents, setContributionCents] = useState(initialContributionCents);
  const [isOther, setIsOther] = useState(false);
  const [provider, setProvider] = useState<MandateProvider | null>(null);

  const providers = useMemo(
    () => MANDATE_PROVIDER_ORDER.filter((slug) => config?.providers.includes(slug)),
    [config],
  );

  useEffect(() => {
    if (provider === null && providers[0]) setProvider(providers[0]);
  }, [providers, provider]);

  if (isPending) {
    return (
      <p className="muted" role="status">
        Loading payment options…
      </p>
    );
  }

  if (error || !config) {
    return (
      <EmptyState
        title="Payment options could not be loaded"
        description="Please reload the page, or contact CalDART if it keeps happening."
      />
    );
  }

  // A membership that never expires cannot renew itself, so it is not offered.
  const renewable = config.plans.filter((entry) => entry.duration_days !== null);
  if ((renewable.length === 0 && !isLifetime) || providers.length === 0) {
    return (
      <EmptyState
        title="Automatic renewal is not available"
        description="This deployment offers no renewing plan that a saved payment method can pay for."
      />
    );
  }

  const offered = renewable.map((entry) => entry.slug);
  const effectivePlan = offered.includes(plan) ? plan : (offered[0] ?? plan);
  const selectedPlan = renewable.find((entry) => entry.slug === effectivePlan) ?? null;
  const planCents = selectedPlan?.price_cents ?? 0;
  const chargeCents = isLifetime ? contributionCents : planCents + contributionCents;
  // The server refuses an authority with nothing to charge, so a life member
  // who has chosen no amount is stopped here rather than at the provider.
  const needsContribution = isLifetime && contributionCents === 0;

  const panelProps = {
    plan: isLifetime ? null : effectivePlan,
    contributionCents,
    nextChargeOn,
    onDone: handleDone,
  };

  return (
    <div className="renewal-setup stack">
      {isLifetime ? null : (
        <PlanChooser plans={renewable} value={effectivePlan} onChange={(next) => setPlan(next)} />
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

      <Field label="First charge on">
        {(props) => (
          <input
            {...props}
            type="date"
            min={earliestChargeOn}
            value={nextChargeOn}
            onChange={(event) => setNextChargeOn(event.target.value)}
          />
        )}
      </Field>

      <p className="renewal-setup__total">
        CalDART will charge <strong className="mono">{formatCents(chargeCents)}</strong> on{' '}
        {formatDate(nextChargeOn)}, and each year after that. We will email you fourteen days
        before every charge.
      </p>

      {needsContribution ? (
        <p className="renewal-setup__blocked" role="status">
          Choose a contribution to charge each year.
        </p>
      ) : (
        <ProviderTabs
          providers={providers}
          active={provider}
          onChange={(next) => setProvider(next)}
        >
          {(current) => (
            <>
              {current === 'stripe' ? (
                <StripeRenewalPanel
                  publishableKey={config.stripe_publishable_key}
                  {...panelProps}
                />
              ) : null}
              {current === 'paypal' ? (
                <PayPalRenewalPanel clientId={config.paypal_client_id} {...panelProps} />
              ) : null}
              {current === 'mock' ? <MockRenewalPanel {...panelProps} /> : null}
            </>
          )}
        </ProviderTabs>
      )}

      <Button variant="quiet" onClick={handleCancel}>
        Cancel
      </Button>
    </div>
  );
}

interface ProviderTabsProps {
  providers: MandateProvider[];
  active: MandateProvider | null;
  onChange: (provider: MandateProvider) => void;
  children: (current: MandateProvider) => JSX.Element;
}

/** The provider tab strip, in the checkout's own shape so the two screens match. */
function ProviderTabs({
  providers,
  active,
  onChange: handleChange,
  children,
}: ProviderTabsProps): JSX.Element | null {
  const selected = active ?? providers[0];
  // `providers` is never empty here: the caller renders the empty state instead.
  if (selected === undefined) return null;
  const current: MandateProvider = selected;

  function handleKeyDown(event: React.KeyboardEvent): void {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const index = providers.indexOf(current);
    const next = providers[(index + step + providers.length) % providers.length];
    if (next) handleChange(next);
  }

  return (
    <section className="checkout__pay">
      <h4 className="eyebrow">Which method should we save?</h4>
      <div className="checkout__tabs" role="tablist" aria-label="Payment method">
        {providers.map((slug) => (
          <button
            key={slug}
            type="button"
            role="tab"
            id={`renewal-tab-${slug}`}
            aria-selected={slug === current}
            aria-controls={`renewal-panel-${slug}`}
            tabIndex={slug === current ? 0 : -1}
            className="checkout__tab"
            onClick={() => handleChange(slug)}
            onKeyDown={handleKeyDown}
          >
            {MANDATE_PROVIDER_LABELS[slug]}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`renewal-panel-${current}`}
        aria-labelledby={`renewal-tab-${current}`}
      >
        {children(current)}
      </div>
    </section>
  );
}
