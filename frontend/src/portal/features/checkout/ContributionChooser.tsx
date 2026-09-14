/**
 * The optional donation added to a membership.
 *
 * The tiers come from the server; "Other amount" and "No thank you" are the
 * two escape hatches every fundraising form needs.
 */
import { useId } from 'react';

import type { ContributionTier } from '../../api/types';
import { formatCents } from '../../components/Money';

export const OTHER = 'other';

export interface ContributionChooserProps {
  tiers: ContributionTier[];
  /** Selected amount in cents. */
  value: number;
  onChange: (cents: number) => void;
  /** True while the member is typing their own amount. */
  isOther: boolean;
  onOther: (isOther: boolean) => void; // codespell:ignore onother
  disabled?: boolean;
}

function label(tier: ContributionTier): string {
  if (tier.cents === 0) return 'No thank you';
  return `${tier.label} · ${formatCents(tier.cents, { whole: true })}`;
}

export function ContributionChooser({
  tiers,
  value,
  onChange,
  isOther,
  onOther, // codespell:ignore onother
  disabled = false,
}: ContributionChooserProps) {
  const otherId = useId();

  return (
    <fieldset className="checkout__section">
      <legend>Add a contribution</legend>
      <p className="muted checkout__hint">
        CalDART is a 501(c)(3); a contribution on top of your dues is tax deductible and pays for
        training, fuel and equipment.
      </p>
      <div className="tier-grid">
        {tiers.map((tier) => (
          <label
            key={tier.cents}
            className="tier-card"
            data-selected={!isOther && tier.cents === value ? 'true' : 'false'}
          >
            <input
              type="radio"
              name="contribution"
              value={tier.cents}
              checked={!isOther && tier.cents === value}
              disabled={disabled}
              onChange={() => {
                onOther(false); // codespell:ignore onother
                onChange(tier.cents);
              }}
            />
            <span>{label(tier)}</span>
          </label>
        ))}
        <label className="tier-card" data-selected={isOther ? 'true' : 'false'}>
          <input
            type="radio"
            name="contribution"
            value={OTHER}
            checked={isOther}
            disabled={disabled}
            onChange={() => onOther(true) /* codespell:ignore onother */}
          />
          <span>Other amount</span>
        </label>
      </div>

      {isOther ? (
        <div className="field checkout__other">
          <label className="field__label" htmlFor={otherId}>
            Contribution amount
          </label>
          <div className="checkout__other-input">
            <span aria-hidden="true" className="mono">
              $
            </span>
            <input
              id={otherId}
              type="number"
              min={0}
              step="1"
              inputMode="decimal"
              disabled={disabled}
              value={value === 0 ? '' : String(value / 100)}
              onChange={(event) => {
                const dollars = Number.parseFloat(event.target.value);
                onChange(Number.isFinite(dollars) && dollars > 0 ? Math.round(dollars * 100) : 0);
              }}
            />
          </div>
        </div>
      ) : null}
    </fieldset>
  );
}
