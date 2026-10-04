import type { JSX } from 'react';

import type { Plan } from '@/portal/api/types';
import { formatCents } from '@/portal/components/Money';

/** The value the friend card reports, which no plan slug takes. */
export const FRIEND_CHOICE = 'friend';

/** The friend card's heading and its one line underneath. */
const FRIEND_HEADING = 'I changed my mind, I just want to be a friend';
const FRIEND_BODY = 'A friend has an account and hears from CalDART, but is not a member.';

export interface PlanChooserProps {
  plans: Plan[];
  value: string;
  onChange: (slug: string) => void;
  /** Disabled while a payment is in flight. */
  disabled?: boolean;
  /**
   * Add a third card after the plans for somebody who would rather be a friend of
   * CalDART than pay dues; choosing it reports `FRIEND_CHOICE`.
   */
  offerFriend?: boolean;
}

function term(plan: Plan): string {
  if (plan.duration_days === null) return 'One payment, membership for life';
  if (plan.duration_days === 365) return 'One year';
  return `${plan.duration_days} days`;
}

/** One radio card: a plan, or the friend card after them. */
interface ChoiceCard {
  value: string;
  name: string;
  /** The formatted price, or null for the friend card, which costs nothing. */
  price: string | null;
  term: string | null;
  description: string;
}

function planCard(plan: Plan): ChoiceCard {
  return {
    value: plan.slug,
    name: plan.name,
    price: formatCents(plan.price_cents),
    term: term(plan),
    description: plan.description,
  };
}

const FRIEND_CARD: ChoiceCard = {
  value: FRIEND_CHOICE,
  name: FRIEND_HEADING,
  price: null,
  term: null,
  description: FRIEND_BODY,
};

/**
 * The plan radio cards at the top of the checkout, with the friend card after them
 * when `offerFriend` is set.
 */
export function PlanChooser({
  plans,
  value,
  onChange,
  disabled = false,
  offerFriend = false,
}: PlanChooserProps): JSX.Element {
  const cards = [...plans.map(planCard), ...(offerFriend ? [FRIEND_CARD] : [])];
  return (
    <fieldset className="checkout__section">
      <legend>Membership</legend>
      <div className="plan-grid">
        {cards.map((card) => (
          <label
            key={card.value}
            className="plan-card"
            data-selected={card.value === value ? 'true' : 'false'}
          >
            <input
              type="radio"
              name="plan"
              value={card.value}
              checked={card.value === value}
              disabled={disabled}
              onChange={() => onChange(card.value)}
            />
            <span className="plan-card__body">
              <span className="plan-card__head">
                <span className="plan-card__name">{card.name}</span>
                {card.price === null ? null : (
                  <span className="plan-card__price num">{card.price}</span>
                )}
              </span>
              {card.term === null ? null : (
                <span className="plan-card__term muted">{card.term}</span>
              )}
              {card.description ? (
                <span className="plan-card__description">{card.description}</span>
              ) : null}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
