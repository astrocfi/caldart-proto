/**
 * The **Bounced** chip an administrator sees beside an address the bounce check found
 * bouncing, on the member record's header and the user record.
 */
import type { JSX } from 'react';

import type { IsoDateTime } from '@/portal/api/types';
import { formatDate } from './DateText';

export interface BouncedChipProps {
  /** When the address last bounced, or `null` when no bounce is known. */
  bouncedAt: IsoDateTime | null;
  /** The bounce report's status code and diagnostic, shown after the chip. */
  detail: string;
}

/**
 * `Bounced MM/DD/YYYY` as a warning chip, followed by the report's detail; nothing at
 * all when the address has no bounce recorded.
 */
export function BouncedChip({ bouncedAt, detail }: BouncedChipProps): JSX.Element | null {
  if (bouncedAt === null) return null;
  return (
    <>
      <span className="chip chip--bad">Bounced {formatDate(bouncedAt)}</span>
      {detail === '' ? null : <span className="muted"> {detail}</span>}
    </>
  );
}
