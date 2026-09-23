import type { JSX } from 'react';

import type { AircraftSummary } from '@/portal/api/types';
import { StatusChip, StatusDot } from '@/portal/components/StatusChip';
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

/** The same state as a dot, for a dense table where a chip in every row shouts. */
export function InsuranceDot({ aircraft, today }: InsuranceChipProps): JSX.Element {
  const tone = insuranceTone(aircraft, today);
  return <StatusDot tone={tone} label={insuranceLabel(tone)} />;
}
