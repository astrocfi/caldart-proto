/**
 * The inline flow that turns automatic renewal on without paying anything.
 *
 * The member picks the plan that will renew, the contribution to renew beside
 * it, and the provider that will hold the method.  Only plans with a duration
 * are offered: a membership for life has nothing to renew.
 *
 * The day of the first charge is the member's own.  It opens on the day their
 * membership runs out, which is the day the charge is wanted on, and it takes any
 * other day from today on.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { IsoDate } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { formatDate, todayIso } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { formatCents } from '@/portal/components/Money';
import { usePaymentsConfig } from '@/portal/features/checkout/api';
import { ContributionChooser } from '@/portal/features/checkout/ContributionChooser';
import { PlanChooser } from '@/portal/features/checkout/PlanChooser';
import { notBeforeToday } from './chargeDate';
import { MandateSetupTabs, mandateProviders } from './MandateSetupTabs';
import '@/portal/features/checkout/checkout.css';

/** The plan a renewal defaults to, where the deployment offers it. */
const DEFAULT_PLAN = 'annual';

export interface RenewalSetupProps {
  /**
   * The day the membership runs out, which the first charge opens on.
   *
   * Null for a member with no term at all, who opens on today instead.
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
  expiresOn = null,
  initialContributionCents = 0,
}: RenewalSetupProps): JSX.Element {
  const { data: config, isPending, error } = usePaymentsConfig();

  const earliestChargeOn = todayIso();
  const [plan, setPlan] = useState<string>(DEFAULT_PLAN);
  const [nextChargeOn, setNextChargeOn] = useState(() => notBeforeToday(expiresOn));
  const [contributionCents, setContributionCents] = useState(initialContributionCents);
  const [isOther, setIsOther] = useState(false);

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
  if (renewable.length === 0 || mandateProviders(config).length === 0) {
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
  const chargeCents = (selectedPlan?.price_cents ?? 0) + contributionCents;
  // An empty box is valid HTML, and an empty date is not a date the API takes, so
  // the provider step waits for one rather than sending it.
  const needsChargeDate = nextChargeOn === '';

  return (
    <div className="renewal-setup stack">
      <PlanChooser plans={renewable} value={effectivePlan} onChange={(next) => setPlan(next)} />

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
            required
            min={earliestChargeOn}
            value={nextChargeOn}
            onChange={(event) => setNextChargeOn(event.target.value)}
          />
        )}
      </Field>

      {needsChargeDate ? (
        <p className="renewal-setup__blocked" role="status">
          Choose the day of the first charge.
        </p>
      ) : (
        <>
          <p className="renewal-setup__total">
            CalDART will charge <strong className="mono">{formatCents(chargeCents)}</strong> on{' '}
            {formatDate(nextChargeOn)}, and each year after that. We will email you fourteen days
            before every charge.
          </p>
          <MandateSetupTabs
            config={config}
            panelProps={{
              scope: 'renewal',
              plan: effectivePlan,
              contributionCents,
              nextChargeOn,
              onDone: handleDone,
            }}
          />
        </>
      )}

      <Button variant="quiet" onClick={handleCancel}>
        Cancel
      </Button>
    </div>
  );
}
