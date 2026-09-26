/**
 * The public donation form: an amount, who is giving, and a payment.
 *
 * The giver chooses an amount (a tier, or one of their own), gives their name, email
 * address, and phone number, may tell us more in a collapsed section, and presses
 * **Continue to payment**.  The details then hold still -- **Change** goes back to
 * them -- and the portal's own provider tabs take the payment through the
 * `/donations/` endpoints.  Once it has gone through the form gives way to one
 * sentence saying where the receipt went, and `onGiven` lets the page show its thanks.
 *
 * A payment method that leaves the page (a card that asks for 3-D Secure) comes back
 * to `returnUrl` with `payment_id` and `token` in the query string; the form then
 * confirms that payment instead of drawing itself.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { DonationsConfig, PaymentProvider } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { formatCents } from '@/portal/components/Money';
import { PROVIDER_ORDER } from '@/portal/features/checkout/api';
import { useSettledPayment } from '@/portal/features/checkout/CheckoutReturn';
import { ContributionChooser } from '@/portal/features/checkout/ContributionChooser';
import type { PaymentEndpoints } from '@/portal/features/checkout/endpoints';
import { ProviderTabs } from '@/portal/features/checkout/ProviderTabs';
import { maskEmail, maskPhone } from '@/portal/masks';
import { donationEndpoints, useDonationsConfig } from './api';
import type { DonorBody } from './api';
import { DonorDetails } from './DonorDetails';
import { EMPTY_DONATION_FORM, donorBody, donorFieldErrors, validateDonation } from './form';
import type { DonationFormErrors, DonationFormValues } from './form';
import './donate.css';

export interface DonationFormProps {
  /** Where the form reads its providers, amounts, and choices from. */
  configUrl: string;
  /** The page a payment method that leaves it comes back to. */
  returnUrl: string;
  /** Called once a gift has gone through, so the page can show its thanks. */
  onGiven?: () => void;
  /** The query string the page was opened with; the address bar's own when left out. */
  search?: string;
}

/** A gift a redirect has brought the browser back for. */
interface Returned {
  paymentId: number;
  token: string;
  paymentIntentId: string;
}

/** The gift `search` names, or null when the page was opened in the ordinary way. */
function readReturn(search: string): Returned | null {
  const params = new URLSearchParams(search);
  const paymentId = Number.parseInt(params.get('payment_id') ?? '', 10);
  const token = params.get('token') ?? '';
  if (!Number.isFinite(paymentId) || token === '') return null;
  return { paymentId, token, paymentIntentId: params.get('payment_intent') ?? '' };
}

/** The public donation form, or the confirmation of a gift a redirect brought back. */
export function DonationForm({
  configUrl,
  returnUrl,
  onGiven,
  search = window.location.search,
}: DonationFormProps): JSX.Element {
  const [returned] = useState(() => readReturn(search));
  const [receiptTo, setReceiptTo] = useState<string | null>(null);

  const handleGiven = useCallback(
    (email: string) => {
      setReceiptTo(email);
      onGiven?.();
    },
    [onGiven],
  );

  if (receiptTo !== null) {
    return (
      <p className="donate__receipt" role="status">
        {receiptTo === ''
          ? 'A receipt is on its way to your email address.'
          : `A receipt is on its way to ${receiptTo}.`}
      </p>
    );
  }
  if (returned !== null) {
    return (
      <DonationReturn returned={returned} returnUrl={returnUrl} onGiven={() => handleGiven('')} />
    );
  }
  return (
    <GiftForm configUrl={configUrl} returnUrl={returnUrl} onGiven={(email) => handleGiven(email)} />
  );
}

interface DonationReturnProps {
  returned: Returned;
  returnUrl: string;
  onGiven: () => void;
}

/** Confirms the gift a redirect method brought the browser back for. */
function DonationReturn({ returned, returnUrl, onGiven }: DonationReturnProps): JSX.Element {
  const endpoints = useMemo(
    () =>
      donationEndpoints({
        returnUrl,
        donor: null,
        tokens: new Map([[returned.paymentId, returned.token]]),
      }),
    [returnUrl, returned],
  );
  const error = useSettledPayment({
    paymentId: returned.paymentId,
    paymentIntentId: returned.paymentIntentId,
    endpoints,
    onSuccess: onGiven,
  });
  if (error !== null) {
    return (
      <EmptyState
        title="Your gift is not confirmed"
        description={error}
        action={
          <a className="button button--secondary" href={returnUrl}>
            Start again
          </a>
        }
      />
    );
  }
  return (
    <p className="muted" role="status" aria-live="polite">
      Confirming your gift…
    </p>
  );
}

interface GiftFormProps {
  configUrl: string;
  returnUrl: string;
  onGiven: (email: string) => void;
}

/** The amount and the giver's details, then the payment. */
function GiftForm({ configUrl, returnUrl, onGiven }: GiftFormProps): JSX.Element {
  const { data: config, isPending, error } = useDonationsConfig(configUrl);
  const [values, setValues] = useState<DonationFormValues>(EMPTY_DONATION_FORM);
  const [amountCents, setAmountCents] = useState(0);
  const [isOther, setIsOther] = useState(false);
  const [errors, setErrors] = useState<DonationFormErrors>({});
  // The details as they stood when the giver pressed Continue; null until then.
  const [donor, setDonor] = useState<DonorBody | null>(null);

  if (isPending) {
    return (
      <p className="muted" role="status">
        Loading the donation form…
      </p>
    );
  }
  if (error || !config) {
    return (
      <EmptyState
        title="The donation form could not be loaded"
        description="Please reload the page, or contact CalDART if it keeps happening."
      />
    );
  }

  if (donor !== null) {
    return (
      <PaymentStep
        config={config}
        donor={donor}
        amountCents={amountCents}
        returnUrl={returnUrl}
        onChange={() => setDonor(null)}
        onGiven={() => onGiven(donor.email)}
        onDonorError={(found) => {
          setErrors((current) => ({ ...current, ...found }));
          setDonor(null);
        }}
      />
    );
  }

  function handleContinue(event: FormEvent): void {
    event.preventDefault();
    const found = validateDonation(values, amountCents);
    setErrors(found);
    if (Object.keys(found).length === 0) setDonor(donorBody(values));
  }

  const set = <Key extends keyof DonationFormValues>(key: Key, next: DonationFormValues[Key]) =>
    setValues((current) => ({ ...current, [key]: next }));

  return (
    <form className="donate stack" noValidate onSubmit={handleContinue}>
      <ContributionChooser
        legend="Amount"
        hint={null}
        tiers={config.contribution_tiers.filter((tier) => tier.cents > 0)}
        value={amountCents}
        maxCents={config.max_contribution_cents}
        onChange={(next) => setAmountCents(next)}
        isOther={isOther}
        // codespell:ignore-next-line onother
        onOther={(next) => {
          setIsOther(next);
          if (next) setAmountCents(0);
        }}
      />
      {errors.amount === undefined ? null : (
        <p className="field__error" role="alert">
          {errors.amount}
        </p>
      )}

      <fieldset>
        <legend>About you</legend>
        <div className="form-grid">
          <Field label="First name" required error={errors.first_name}>
            {(props) => (
              <input
                {...props}
                name="first_name"
                autoComplete="given-name"
                value={values.first_name}
                onChange={(event) => set('first_name', event.target.value)}
              />
            )}
          </Field>
          <Field label="Last name" required error={errors.last_name}>
            {(props) => (
              <input
                {...props}
                name="last_name"
                autoComplete="family-name"
                value={values.last_name}
                onChange={(event) => set('last_name', event.target.value)}
              />
            )}
          </Field>
          <Field label="Email" required error={errors.email} hint="Your receipt goes here">
            {(props) => (
              <MaskedInput
                {...props}
                type="email"
                name="email"
                autoComplete="email"
                mask={maskEmail}
                value={values.email}
                onValueChange={(next) => set('email', next)}
              />
            )}
          </Field>
          <Field label="Phone" required error={errors.phone}>
            {(props) => (
              <MaskedInput
                {...props}
                type="tel"
                inputMode="tel"
                name="phone"
                autoComplete="tel"
                placeholder="415-555-0100"
                mask={maskPhone}
                value={values.phone}
                onValueChange={(next) => set('phone', next)}
              />
            )}
          </Field>
        </div>
      </fieldset>

      <DonorDetails value={values} onChange={(next) => setValues(next)} config={config} />

      <div className="cluster">
        <Button type="submit">Continue to payment</Button>
      </div>
    </form>
  );
}

interface PaymentStepProps {
  config: DonationsConfig;
  donor: DonorBody;
  amountCents: number;
  returnUrl: string;
  onChange: () => void;
  onGiven: () => void;
  /**
   * The server refused the checkout on one of the details form's own fields; handed
   * the message for each one, so the giver sees it beside the field that earned it
   * rather than only in the payment panel.
   */
  onDonorError: (found: Partial<Record<keyof DonationFormValues, string>>) => void;
}

/** What is being given and by whom, with a way back, then the provider tabs. */
function PaymentStep({
  config,
  donor,
  amountCents,
  returnUrl,
  onChange: handleChange,
  onGiven,
  onDonorError,
}: PaymentStepProps): JSX.Element {
  const providers = useMemo(
    () => PROVIDER_ORDER.filter((slug) => config.providers.includes(slug)),
    [config],
  );
  const [provider, setProvider] = useState<PaymentProvider | null>(null);
  // Wraps the ordinary donation endpoints so a field-level refusal reaches the
  // giver beside the field it named, in addition to whatever the payment panel
  // itself shows: the panel does not know the donation form's own fields.
  const endpoints = useMemo<PaymentEndpoints>(() => {
    const base = donationEndpoints({ returnUrl, donor });
    return {
      ...base,
      createCheckout: async (request, signal) => {
        try {
          return await base.createCheckout(request, signal);
        } catch (caught) {
          const found = donorFieldErrors(caught);
          if (Object.keys(found).length > 0) onDonorError(found);
          throw caught;
        }
      },
    };
  }, [returnUrl, donor, onDonorError]);

  useEffect(() => {
    if (provider === null && providers[0]) setProvider(providers[0]);
  }, [providers, provider]);

  return (
    <section className="donate stack">
      <div className="donate__summary">
        <p>
          You are giving <strong className="mono">{formatCents(amountCents)}</strong> as{' '}
          {donor.first_name} {donor.last_name} ({donor.email}).
        </p>
        <Button variant="quiet" onClick={() => handleChange()}>
          Change
        </Button>
      </div>
      {providers.length === 0 ? (
        <EmptyState
          title="Online giving is not set up yet"
          description="Please contact CalDART to give by check, or try again later."
        />
      ) : (
        <ProviderTabs
          providers={providers}
          active={provider}
          onChange={(next) => setProvider(next)}
          config={config}
          panelProps={{
            plan: null,
            contributionCents: amountCents,
            amountCents,
            autoRenew: false,
            endpoints,
            onSuccess: () => onGiven(),
          }}
        />
      )}
    </section>
  );
}
