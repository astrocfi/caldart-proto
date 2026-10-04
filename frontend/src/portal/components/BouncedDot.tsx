/**
 * The **Bounced** status an administrator sees beside an address the bounce check found
 * bouncing, on the member record's header and the user record.
 */
import type { JSX } from 'react';

import type { IsoDateTime } from '@/portal/api/types';
import { formatDate } from './DateText';
import { StatusDot } from './StatusDot';

export interface BouncedDotProps {
  /** When the address last bounced, or `null` when no bounce is known. */
  bouncedAt: IsoDateTime | null;
  /** The bounce report's status code and diagnostic, shown after the status. */
  detail: string;
}

/**
 * `Bounced MM/DD/YYYY` after a red dot, followed by the report's detail; nothing at all
 * when the address has no bounce recorded.
 */
export function BouncedDot({ bouncedAt, detail }: BouncedDotProps): JSX.Element | null {
  if (bouncedAt === null) return null;
  return (
    <>
      <StatusDot tone="expired" label={`Bounced ${formatDate(bouncedAt)}`} />
      {detail === '' ? null : <span className="muted"> {detail}</span>}
    </>
  );
}
