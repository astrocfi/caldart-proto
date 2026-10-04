import type { JSX } from 'react';

import type { AircraftSummary } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { StatusDot, datedWord } from '@/portal/components/StatusDot';
import { insuranceLabel, insuranceTone } from './insurance';

export interface InsuranceDotProps {
  aircraft: Pick<AircraftSummary, 'insurance_is_current' | 'insurance_expiration'>;
  today?: Date;
  /**
   * Put the date in the word, for a column of expiry dates: "Insured to 04/29/2027",
   * "Expiring 10/31/2026", or "Expired 03/02/2026".
   */
  withDate?: boolean;
}

/**
 * The one status that says whether a plane may fly, used on every screen: a dot and
 * its word (Insured, Expiring soon, Insurance expired, or Not on file), with the
 * expiry date on hover.
 */
export function InsuranceDot({
  aircraft,
  today,
  withDate = false,
}: InsuranceDotProps): JSX.Element {
  const tone = insuranceTone(aircraft, today);
  const date = aircraft.insurance_expiration;
  if (withDate && date && tone !== 'none') {
    return <StatusDot tone={tone} label={datedWord(tone, 'Insured to', formatDate(date))} />;
  }
  return (
    <StatusDot
      tone={tone}
      label={insuranceLabel(tone)}
      title={date ? `Runs to ${formatDate(date)}` : undefined}
    />
  );
}
