import type { JSX } from 'react';

import type { AircraftSummary } from '../../api/types';
import { StatusChip } from '../../components/StatusChip';
import { insuranceLabel, insuranceTone } from './insurance';

export interface InsuranceChipProps {
  aircraft: Pick<AircraftSummary, 'insurance_is_current' | 'insurance_expiration'>;
  today?: Date;
}

/** The one chip that says whether a plane may fly, used on every screen. */
export function InsuranceChip({ aircraft, today }: InsuranceChipProps): JSX.Element {
  const tone = insuranceTone(aircraft, today);
  return (
    <StatusChip
      tone={tone}
      label={insuranceLabel(tone)}
      title={aircraft.insurance_expiration ?? undefined}
    />
  );
}
