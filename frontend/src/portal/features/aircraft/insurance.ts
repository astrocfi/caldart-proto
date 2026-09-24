/**
 * Aircraft helpers shared by the picker, the admin register and the leader
 * check: N-number normalization (the same rule as the server) and the
 * insurance state every screen colors its chips by.
 */
import type { AircraftSummary } from '@/portal/api/types';
import { EXPIRING_WINDOW_DAYS, daysUntil } from '@/portal/components/StatusChip';
import type { StatusTone } from '@/portal/components/StatusChip';

const PUNCTUATION = /[^A-Za-z0-9]/g;

/**
 * `12345`, `n12345`, and `N-12345` are all `N12345`.
 *
 * Mirrors `apps.aircraft.models.normalize_n_number` so the UI can show the
 * canonical form before the round trip.
 */
export function normalizeNNumber(value: string): string {
  const cleaned = value.replace(PUNCTUATION, '').toUpperCase();
  if (!cleaned) return '';
  return /^\d/.test(cleaned) ? `N${cleaned}` : cleaned;
}

/** True when a search term could be a registration: a registration has digits. */
export function looksLikeRegistration(value: string): boolean {
  return /\d/.test(value);
}

/** Insurance currency as one of the four chip tones. */
export function insuranceTone(
  aircraft: Pick<AircraftSummary, 'insurance_is_current' | 'insurance_expiration'>,
  today: Date = new Date(),
): StatusTone {
  if (!aircraft.insurance_expiration) return 'none';
  if (!aircraft.insurance_is_current) return 'expired';
  const days = daysUntil(aircraft.insurance_expiration, today);
  return days !== null && days <= EXPIRING_WINDOW_DAYS ? 'expiring' : 'current';
}

const INSURANCE_LABEL: Record<StatusTone, string> = {
  current: 'Insured',
  expiring: 'Expiring soon',
  // Insurance is never "new": the tone exists for a membership nobody has paid
  // for yet, and the record either has a policy on it or it does not.
  new: 'No insurance on file',
  expired: 'Insurance expired',
  none: 'No insurance on file',
};

/** The chip text for an insurance tone. */
export function insuranceLabel(tone: StatusTone): string {
  return INSURANCE_LABEL[tone];
}

/** `"1,000,000"` typed into a dollars box becomes 100000000 cents. */
export function dollarsToCents(value: string): number | null {
  const cleaned = value.replace(/[$,\s]/g, '');
  if (!cleaned) return null;
  const amount = Number(cleaned);
  if (!Number.isFinite(amount) || amount < 0) return null;
  return Math.round(amount * 100);
}

/** Cents back into a dollars string for an editable input, with thousands commas. */
export function centsToDollars(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return '';
  const dollars = cents / 100;
  return dollars.toLocaleString('en-US', {
    minimumFractionDigits: Number.isInteger(dollars) ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

/**
 * A half-typed amount, grouped for reading: `1000000` shows as `1,000,000`.
 *
 * Returns the text unchanged when it is not a number, so somebody mid-edit is
 * never fighting the field; `dollarsToCents` strips the commas again on the way
 * out.
 */
export function formatDollars(typed: string): string {
  const cents = dollarsToCents(typed);
  return cents === null ? typed : centsToDollars(cents);
}
