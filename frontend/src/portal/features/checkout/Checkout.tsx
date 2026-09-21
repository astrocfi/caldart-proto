/**
 * The shared checkout widget used by both `/join` and `/renew`.
 *
 * Choose a plan, optionally add a contribution, then pay with whichever
 * providers this deployment has keys for.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { PaymentProvider } from '../../api/types';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { formatCents } from '../../components/Money';
import { PROVIDER_LABELS, PROVIDER_ORDER, usePaymentsConfig } from './api';
import { ContributionChooser } from './ContributionChooser';
import { MockPanel } from './MockPanel';
import { PayPalPanel } from './PayPalPanel';
import { PlanChooser } from './PlanChooser';
import { StripePanel } from './StripePanel';
import type { CheckoutProps, CheckoutResult } from './types';
import './checkout.css';

/** Renewals default to the annual plan. */
const DEFAULT_PLAN = 'annual';

export type { CheckoutProps, CheckoutResult } from './types';

/** Choose a plan and a contribution, then pay with the configured providers. */
export function Checkout({ mode, onSuccess }: CheckoutProps): JSX.Element {
  const queryClient = useQueryClient();
  const { data: config, isPending, error } = usePaymentsConfig();

  const [plan, setPlan] = useState<string>(DEFAULT_PLAN);
  const [contributionCents, setContributionCents] = useState(0);
  const [isOther, setIsOther] = useState(false);
  const [provider, setProvider] = useState<PaymentProvider | null>(null);

  const providers = useMemo(
    () => PROVIDER_ORDER.filter((slug) => config?.providers.includes(slug)),
    [config],
  );

  useEffect(() => {
    if (provider === null && providers[0]) setProvider(providers[0]);
  }, [providers, provider]);

  if (isPending) {
    return (
      <Card eyebrow={mode === 'renew' ? 'Renewal' : 'Membership'} title="Payment">
        <p className="muted" role="status">
          Loading payment options…
        </p>
      </Card>
    );
  }

  if (error || !config) {
    return (
      <Card eyebrow={mode === 'renew' ? 'Renewal' : 'Membership'} title="Payment">
        <EmptyState
          title="Payment options could not be loaded"
          description="Please reload the page, or contact CalDART if it keeps happening."
        />
      </Card>
    );
  }

  // "Annual" is only the default where the server offers it; anywhere else the
  // first plan on the list stands in, so the chooser always has a selection.
  const offered = config.plans.map((entry) => entry.slug);
  const effectivePlan = offered.includes(plan) ? plan : (offered[0] ?? plan);

  const selectedPlan = config.plans.find((entry) => entry.slug === effectivePlan) ?? null;
  const planCents = selectedPlan?.price_cents ?? 0;
  const totalCents = planCents + contributionCents;

  function handleSuccess(result: CheckoutResult) {
    void queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    void queryClient.invalidateQueries({ queryKey: ['membership'] });
    onSuccess(result);
  }

  const panelProps = {
    plan: effectivePlan,
    contributionCents,
    amountCents: totalCents,
    onSuccess: handleSuccess,
  };

  return (
    <Card
      eyebrow={mode === 'renew' ? 'Renewal' : 'Membership'}
      title={mode === 'renew' ? 'Renew your membership' : 'Join CalDART'}
      className="checkout"
    >
      <PlanChooser plans={config.plans} value={effectivePlan} onChange={setPlan} />

      <ContributionChooser
        tiers={config.contribution_tiers}
        value={contributionCents}
        onChange={setContributionCents}
        isOther={isOther}
        // codespell:ignore-next-line onother
        onOther={(next) => {
          setIsOther(next);
          if (next) setContributionCents(0);
        }}
      />

      <dl className="checkout__total">
        <div>
          <dt>{selectedPlan?.name ?? 'Membership'}</dt>
          <dd className="mono">{formatCents(planCents)}</dd>
        </div>
        {contributionCents > 0 ? (
          <div>
            <dt>Contribution</dt>
            <dd className="mono">{formatCents(contributionCents)}</dd>
          </div>
        ) : null}
        <div className="checkout__total-row">
          <dt>Total today</dt>
          <dd className="mono" data-testid="checkout-total">
            {formatCents(totalCents)}
          </dd>
        </div>
      </dl>

      {providers.length === 0 ? (
        <EmptyState
          title="Online payment is not set up yet"
          description="Please contact CalDART to pay by check, or try again later."
        />
      ) : (
        <ProviderTabs
          providers={providers}
          active={provider}
          onChange={setProvider}
          config={config}
          panelProps={panelProps}
        />
      )}
    </Card>
  );
}

interface ProviderTabsProps {
  providers: PaymentProvider[];
  active: PaymentProvider | null;
  onChange: (provider: PaymentProvider) => void;
  config: { stripe_publishable_key: string; paypal_client_id: string };
  panelProps: {
    plan: string;
    contributionCents: number;
    amountCents: number;
    onSuccess: (result: CheckoutResult) => void;
  };
}

function ProviderTabs({ providers, active, onChange, config, panelProps }: ProviderTabsProps) {
  const current = active ?? providers[0]!;

  function handleKeyDown(event: React.KeyboardEvent): void {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const index = providers.indexOf(current);
    const next = providers[(index + step + providers.length) % providers.length];
    if (next) onChange(next);
  }

  return (
    <section className="checkout__pay">
      <h3 className="eyebrow">How would you like to pay?</h3>
      <div className="checkout__tabs" role="tablist" aria-label="Payment method">
        {providers.map((slug) => (
          <button
            key={slug}
            type="button"
            role="tab"
            id={`checkout-tab-${slug}`}
            aria-selected={slug === current}
            aria-controls={`checkout-panel-${slug}`}
            tabIndex={slug === current ? 0 : -1}
            className="checkout__tab"
            onClick={() => onChange(slug)}
            onKeyDown={handleKeyDown}
          >
            {PROVIDER_LABELS[slug]}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`checkout-panel-${current}`}
        aria-labelledby={`checkout-tab-${current}`}
      >
        {current === 'stripe' ? (
          <StripePanel publishableKey={config.stripe_publishable_key} {...panelProps} />
        ) : null}
        {current === 'paypal' ? (
          <PayPalPanel clientId={config.paypal_client_id} {...panelProps} />
        ) : null}
        {current === 'mock' ? <MockPanel {...panelProps} /> : null}
      </div>
    </section>
  );
}
