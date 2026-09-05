/** The plan radio cards at the top of the checkout (PLAN §6.7). */
import type { Plan } from '../../api/types';
import { formatCents } from '../../components/Money';

export interface PlanChooserProps {
  plans: Plan[];
  value: string;
  onChange: (slug: string) => void;
  /** Disabled while a payment is in flight. */
  disabled?: boolean;
}

function term(plan: Plan): string {
  if (plan.duration_days === null) return 'One payment, membership for life';
  if (plan.duration_days === 365) return 'One year';
  return `${plan.duration_days} days`;
}

export function PlanChooser({ plans, value, onChange, disabled = false }: PlanChooserProps) {
  return (
    <fieldset className="checkout__section">
      <legend>Membership</legend>
      <div className="plan-grid">
        {plans.map((plan) => (
          <label
            key={plan.slug}
            className="plan-card"
            data-selected={plan.slug === value ? 'true' : 'false'}
          >
            <input
              type="radio"
              name="plan"
              value={plan.slug}
              checked={plan.slug === value}
              disabled={disabled}
              onChange={() => onChange(plan.slug)}
            />
            <span className="plan-card__body">
              <span className="plan-card__head">
                <span className="plan-card__name">{plan.name}</span>
                <span className="plan-card__price mono">{formatCents(plan.price_cents)}</span>
              </span>
              <span className="plan-card__term muted">{term(plan)}</span>
              {plan.description ? (
                <span className="plan-card__description">{plan.description}</span>
              ) : null}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
