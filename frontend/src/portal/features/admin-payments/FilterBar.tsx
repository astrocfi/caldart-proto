/**
 * The finance list's filter bar.
 *
 * The bar is fully controlled: every control writes straight back to the
 * filter state.  Debouncing the search box is the list screen's job, because
 * it owns the query the box is really typing into.
 */
import type { JSX } from 'react';

import { usePlans } from '@/portal/api/queries';
import type { PaymentKind, PaymentProvider, PaymentState, PaymentWallet } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { EMPTY_FILTERS } from './api';
import type { PaymentFilterState, ReconciledFilter } from './api';
import { KIND_LABELS, PROVIDER_LABELS, STATUS_LABELS, WALLET_LABELS } from './labels';

export interface FilterBarProps {
  value: PaymentFilterState;
  onChange: (filters: PaymentFilterState) => void;
  /** Hide the controls the overview has no use for. */
  compact?: boolean;
}

const PROVIDERS: PaymentProvider[] = ['stripe', 'paypal', 'mock', 'manual'];
const STATUSES: PaymentState[] = [
  'succeeded',
  'pending',
  'failed',
  'partially_refunded',
  'refunded',
];
const KINDS: PaymentKind[] = ['membership', 'contribution', 'both'];
const WALLETS: PaymentWallet[] = [
  'card',
  'apple_pay',
  'google_pay',
  'link',
  'paypal',
  'check',
  'cash',
  'bank_transfer',
  'other',
];
const RECONCILED: { value: ReconciledFilter; label: string }[] = [
  { value: '', label: 'Matched or not' },
  { value: 'yes', label: 'Matched' },
  { value: 'no', label: 'Not matched' },
];

/** Dollars typed into an amount box as the cents the API filters on. */
export function centsFromDollars(typed: string): string {
  const trimmed = typed.trim();
  if (trimmed === '') return '';
  const dollars = Number(trimmed);
  if (!Number.isFinite(dollars) || dollars < 0) return '';
  return String(Math.round(dollars * 100));
}

/** Cents as the dollars an amount box shows, or `''` for no bound at all. */
export function dollarsFromCents(cents: string): string {
  if (cents === '') return '';
  const value = Number(cents);
  return Number.isFinite(value) ? String(value / 100) : '';
}

/** The finance list's filter bar: dates, provider, status, plan, kind and amounts. */
export function FilterBar({ value, onChange, compact = false }: FilterBarProps): JSX.Element {
  const plans = usePlans();

  function set<K extends keyof PaymentFilterState>(key: K, next: PaymentFilterState[K]) {
    onChange({ ...value, [key]: next });
  }

  function handleClear() {
    onChange(EMPTY_FILTERS);
  }

  const isFiltered = Object.values(value).some((entry) => entry !== '');

  return (
    <div className="payment-filters">
      <Field label="From">
        {(props) => (
          <input
            {...props}
            type="date"
            value={value.from}
            onChange={(event) => set('from', event.target.value)}
          />
        )}
      </Field>
      <Field label="To">
        {(props) => (
          <input
            {...props}
            type="date"
            value={value.to}
            onChange={(event) => set('to', event.target.value)}
          />
        )}
      </Field>
      <Field label="Provider">
        {(props) => (
          <select
            {...props}
            value={value.provider}
            onChange={(event) => set('provider', event.target.value as PaymentProvider | '')}
          >
            <option value="">Any provider</option>
            {PROVIDERS.map((provider) => (
              <option key={provider} value={provider}>
                {PROVIDER_LABELS[provider]}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Status">
        {(props) => (
          <select
            {...props}
            value={value.status}
            onChange={(event) => set('status', event.target.value as PaymentState | '')}
          >
            <option value="">Any status</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        )}
      </Field>
      {compact ? null : (
        <>
          <Field label="Plan">
            {(props) => (
              <select
                {...props}
                value={value.plan}
                onChange={(event) => set('plan', event.target.value)}
              >
                <option value="">Any plan</option>
                {(plans.data ?? []).map((plan) => (
                  <option key={plan.slug} value={plan.slug}>
                    {plan.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="For">
            {(props) => (
              <select
                {...props}
                value={value.kind}
                onChange={(event) => set('kind', event.target.value as PaymentKind | '')}
              >
                <option value="">Dues or gifts</option>
                {KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND_LABELS[kind]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Method">
            {(props) => (
              <select
                {...props}
                value={value.wallet}
                onChange={(event) => set('wallet', event.target.value as PaymentWallet | '')}
              >
                <option value="">Any method</option>
                {WALLETS.map((wallet) => (
                  <option key={wallet} value={wallet}>
                    {WALLET_LABELS[wallet]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Reconciled">
            {(props) => (
              <select
                {...props}
                value={value.reconciled}
                onChange={(event) => set('reconciled', event.target.value as ReconciledFilter)}
              >
                {RECONCILED.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="At least" hint="Dollars">
            {(props) => (
              <input
                {...props}
                type="number"
                min="0"
                step="0.01"
                value={dollarsFromCents(value.min_cents)}
                onChange={(event) => set('min_cents', centsFromDollars(event.target.value))}
              />
            )}
          </Field>
          <Field label="At most" hint="Dollars">
            {(props) => (
              <input
                {...props}
                type="number"
                min="0"
                step="0.01"
                value={dollarsFromCents(value.max_cents)}
                onChange={(event) => set('max_cents', centsFromDollars(event.target.value))}
              />
            )}
          </Field>
        </>
      )}
      <Field label="Search" hint="Name, email, reference, or note">
        {(props) => (
          <input
            {...props}
            type="search"
            value={value.search}
            onChange={(event) => set('search', event.target.value)}
          />
        )}
      </Field>
      {isFiltered ? (
        <Button variant="quiet" small onClick={handleClear}>
          Clear filters
        </Button>
      ) : null}
    </div>
  );
}
