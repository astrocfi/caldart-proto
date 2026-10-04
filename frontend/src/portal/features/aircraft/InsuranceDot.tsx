import type { JSX } from 'react';

import type { AircraftSummary } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { StatusDot } from '@/portal/components/StatusDot';
import { insuranceLabel, insuranceTone } from './insurance';

export interface InsuranceDotProps {
  aircraft: Pick<AircraftSummary, 'insurance_is_current' | 'insurance_expiration'>;
  today?: Date;
  /** Hide the word where the expiry date beside the dot already says it. */
  hideWord?: boolean;
}

/**
 * The one status that says whether a plane may fly, used on every screen: a dot and
 * its word (Insured, Expiring soon, Insurance expired, or Not on file), with the
 * expiry date on hover.
 */
export function InsuranceDot({
  aircraft,
  today,
  hideWord = false,
}: InsuranceDotProps): JSX.Element {
  const tone = insuranceTone(aircraft, today);
  return (
    <StatusDot
      tone={tone}
      label={insuranceLabel(tone)}
      title={
        !hideWord && aircraft.insurance_expiration
          ? `Runs to ${formatDate(aircraft.insurance_expiration)}`
          : undefined
      }
      hideWord={hideWord}
    />
  );
}
