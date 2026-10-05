/**
 * The provider tabs under a checkout: one tab per configured provider, and the
 * chosen provider's panel beneath them.
 *
 * The portal's checkout and the public donation form both render this; the panel
 * props say what is being paid for, and their `endpoints` which server calls pay it.
 * Left and right arrows move between the tabs.
 */
import type { JSX } from 'react';

import type { PaymentProvider } from '@/portal/api/types';
import { Heading } from '@/portal/components/Heading';
import { PROVIDER_LABELS } from './api';
import { MockPanel } from './MockPanel';
import { PayPalPanel } from './PayPalPanel';
import { StripePanel } from './StripePanel';
import type { CheckoutHeadingLevel, ProviderPanelProps } from './types';
import './checkout.css';

export interface ProviderTabsProps {
  providers: PaymentProvider[];
  active: PaymentProvider | null;
  onChange: (provider: PaymentProvider) => void;
  config: { stripe_publishable_key: string; paypal_client_id: string };
  panelProps: ProviderPanelProps;
  /** The level of the heading over the tabs, one under the heading of what holds them. */
  headingLevel?: CheckoutHeadingLevel;
}

/** The tab list for `providers`, and the active provider's panel below it. */
export function ProviderTabs({
  providers,
  active,
  onChange,
  config,
  panelProps,
  headingLevel = 3,
}: ProviderTabsProps): JSX.Element | null {
  const selected = active ?? providers[0];
  // `providers` is never empty here: the caller renders the empty state instead.
  if (selected === undefined) return null;
  const current: PaymentProvider = selected;

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
      <Heading level={headingLevel} className="eyebrow">
        How would you like to pay?
      </Heading>
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
