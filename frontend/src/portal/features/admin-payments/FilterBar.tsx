/** The payment report's filter bar. */
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import type { PaymentProvider, PaymentState } from '@/portal/api/types';
import { EMPTY_FILTERS } from './api';
import type { PaymentFilterState } from './api';
import { PROVIDER_LABELS, STATUS_LABELS } from './labels';

export interface FilterBarProps {
  value: PaymentFilterState;
  onChange: (filters: PaymentFilterState) => void;
}

const PROVIDERS: PaymentProvider[] = ['stripe', 'paypal', 'mock'];
const STATUSES: PaymentState[] = ['succeeded', 'pending', 'failed', 'refunded'];

/** The payment report's filter bar: date range, provider, status, and search. */
export function FilterBar({ value, onChange }: FilterBarProps): JSX.Element {
  function set<K extends keyof PaymentFilterState>(key: K, next: PaymentFilterState[K]) {
    onChange({ ...value, [key]: next });
  }

  const isFiltered = Object.values(value).some(Boolean);

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
      <Field label="Search" hint="Name, email, or provider reference">
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
        <Button variant="quiet" small onClick={() => onChange(EMPTY_FILTERS)}>
          Clear filters
        </Button>
      ) : null}
    </div>
  );
}
