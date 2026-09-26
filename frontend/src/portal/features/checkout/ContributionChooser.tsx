/**
 * The optional donation added to a membership.
 *
 * The tiers come from the server; "Other amount" and "No thank you" are the
 * two escape hatches every fundraising form needs.
 */
import { useId } from 'react';
import type { JSX } from 'react';

import type { ContributionTier } from '@/portal/api/types';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { formatCents } from '@/portal/components/Money';
import { maskWholeDollars } from '@/portal/masks';

export const OTHER = 'other';

/** Enough digits for the largest contribution the server accepts. */
const DOLLAR_DIGITS = 6;

/** A grouped dollar amount as integer cents; a blank box is nothing given. */
export function dollarsToCents(typed: string): number {
  const digits = typed.replace(/\D/g, '');
  return digits ? Number(digits) * 100 : 0;
}

/**
 * Whole dollars, grouped, and never more than the server accepts.
 *
 * The cap is applied as the amount is typed, so a digit too many is refused at
 * the keyboard rather than at the payment provider.  A `maxCents` of `null` is
 * a cap not yet known, and caps nothing.
 */
export function maskContribution(raw: string, maxCents: number | null): string {
  const masked = maskWholeDollars(raw, DOLLAR_DIGITS);
  if (maxCents === null) return masked;
  const cents = dollarsToCents(masked);
  return cents > maxCents ? maskWholeDollars(String(Math.floor(maxCents / 100))) : masked;
}

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
  /** The fieldset's legend; a checkout adds a contribution to its dues. */
  legend?: string;
  /** The line under the legend; null for none. */
  hint?: string | null;
}

/** What the chooser says over a contribution added to dues. */
const DUES_HINT =
  'CalDART is a 501(c)(3); a contribution on top of your dues is tax deductible and pays for ' +
  'training, fuel, and equipment.';

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
  legend = 'Add a contribution',
  hint = DUES_HINT,
}: ContributionChooserProps): JSX.Element {
  const otherId = useId();

  const maskAmount = (raw: string): string => maskContribution(raw, maxCents);

  return (
    <fieldset className="checkout__section">
      <legend>{legend}</legend>
      {hint === null ? null : <p className="muted checkout__hint">{hint}</p>}
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
            <MaskedInput
              id={otherId}
              className="mono"
              inputMode="numeric"
              aria-describedby={`${otherId}-hint`}
              disabled={disabled}
              mask={maskAmount}
              value={value === 0 ? '' : maskWholeDollars(String(Math.floor(value / 100)))}
              onValueChange={(next) => onChange(dollarsToCents(next))}
            />
          </div>
        </div>
      ) : null}
    </fieldset>
  );
}
