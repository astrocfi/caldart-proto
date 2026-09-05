import type { Aircraft } from '../../api/types';
import { StatusChip } from '../../components/StatusChip';

export interface ServiceChipProps {
  aircraft: Pick<Aircraft, 'is_active'>;
}

/**
 * "Out of service", or nothing at all.
 *
 * An administrator clears the in-service flag on an airframe that is grounded
 * or sold; every screen that offers an aeroplane says so, rather than letting
 * the flag be a field that only the form ever reads.
 */
export function ServiceChip({ aircraft }: ServiceChipProps) {
  if (aircraft.is_active) return null;
  return <StatusChip tone="none" label="Out of service" />;
}
