/**
 * The optional donation added to a membership.
 *
 * The tiers come from the server; "Other amount" and "No thank you" are the
 * two escape hatches every fundraising form needs.
 */
import { useId } from 'react';
import type { JSX } from 'react';

import type { ContributionTier } from '@/portal/api/types';
import { formatCents } from '@/portal/components/Money';

export const OTHER = 'other';

export interface ContributionChooserProps {
  tiers: ContributionTier[];
  /** Selected amount in cents. */
  value: number;
  onChange: (cents: number) => void;
  /** The largest amount the server will accept, in cents. */
  maxCents: number;
  /** True while the member is typing their own amount. */
  isOther: boolean;
  onOther: (isOther: boolean) => void; // codespell:ignore onother
  disabled?: boolean;
}

function label(tier: ContributionTier): string {
  if (tier.cents === 0) return 'No thank you';
  return `${tier.label} · ${formatCents(tier.cents, { whole: true })}`;
}

/** The contribution tier cards, plus an "Other amount" input. */
export function ContributionChooser({
  tiers,
  value,
  onChange,
  maxCents,
  isOther,
  onOther, // codespell:ignore onother
  disabled = false,
}: ContributionChooserProps): JSX.Element {
  const otherId = useId();

  return (
    <fieldset className="checkout__section">
      <legend>Add a contribution</legend>
      <p className="muted checkout__hint">
        CalDART is a 501(c)(3); a contribution on top of your dues is tax deductible and pays for
        training, fuel, and equipment.
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
          <p className="field__hint" id={`${otherId}-hint`}>
            Up to {formatCents(maxCents, { whole: true })}. For more than that, talk to the
            treasurer.
          </p>
          <div className="checkout__other-input">
            <span aria-hidden="true" className="mono">
              $
            </span>
            <input
              id={otherId}
              type="number"
              min={0}
              max={maxCents / 100}
              step="1"
              inputMode="decimal"
              aria-describedby={`${otherId}-hint`}
              disabled={disabled}
              value={value === 0 ? '' : String(value / 100)}
              onChange={(event) => {
                const dollars = Number.parseFloat(event.target.value);
                if (!Number.isFinite(dollars) || dollars <= 0) {
                  onChange(0);
                  return;
                }
                // Clamp rather than reject: a typed digit too many should not
                // discard what the member meant, and the server refuses
                // anything above this anyway.
                onChange(Math.min(Math.round(dollars * 100), maxCents));
              }}
            />
          </div>
        </div>
      ) : null}
    </fieldset>
  );
}
