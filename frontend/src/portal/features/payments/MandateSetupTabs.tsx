/**
 * The provider tabs of every flow that saves a method for later charges.
 *
 * Automatic renewal's setup on the Payments screen and a recurring donation that
 * starts on a later day both offer the same tabs over the same three panels, so
 * they render this rather than two copies of it.
 */
import { useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { MandateProvider, PaymentsConfig } from '@/portal/api/types';
import { MockRenewalPanel } from './MockRenewalPanel';
import { PayPalRenewalPanel } from './PayPalRenewalPanel';
import { StripeRenewalPanel } from './StripeRenewalPanel';
import type { RenewalPanelProps } from './types';
import { MANDATE_PROVIDER_LABELS, MANDATE_PROVIDER_ORDER } from './types';

/** The providers of `config` that can hold a saved method, in tab order. */
export function mandateProviders(config: PaymentsConfig | undefined): MandateProvider[] {
  return MANDATE_PROVIDER_ORDER.filter((slug) => config?.providers.includes(slug));
}

export interface MandateSetupTabsProps {
  config: PaymentsConfig;
  /** What every panel is handed. */
  panelProps: RenewalPanelProps;
}

/**
 * One tab per provider that can hold a saved method, over that provider's panel.
 *
 * Renders nothing when the deployment offers no such provider; the caller says so.
 */
export function MandateSetupTabs({
  config,
  panelProps,
}: MandateSetupTabsProps): JSX.Element | null {
  const providers = useMemo(() => mandateProviders(config), [config]);
  const [active, setActive] = useState<MandateProvider | null>(null);

  useEffect(() => {
    if (active === null && providers[0]) setActive(providers[0]);
  }, [providers, active]);

  const selected = active ?? providers[0];
  if (selected === undefined) return null;
  const current: MandateProvider = selected;

  function handleKeyDown(event: React.KeyboardEvent): void {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const index = providers.indexOf(current);
    const next = providers[(index + step + providers.length) % providers.length];
    if (next) setActive(next);
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
            onClick={() => setActive(slug)}
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
        {current === 'stripe' ? (
          <StripeRenewalPanel publishableKey={config.stripe_publishable_key} {...panelProps} />
        ) : null}
        {current === 'paypal' ? (
          <PayPalRenewalPanel clientId={config.paypal_client_id} {...panelProps} />
        ) : null}
        {current === 'mock' ? <MockRenewalPanel {...panelProps} /> : null}
      </div>
    </section>
  );
}
