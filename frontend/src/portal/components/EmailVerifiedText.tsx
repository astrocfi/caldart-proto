import type { JSX } from 'react';

import type { IsoDateTime } from '@/portal/api/types';
import { DateText } from './DateText';

export interface EmailVerifiedTextProps {
  /** When the account's current email address was verified, or `null` if it has not been. */
  verifiedAt: IsoDateTime | null;
}

/**
 * `Verified <date>` or `Unverified`, from when an account's email address was verified.
 *
 * Shared by the user detail screen and the member record's profile tab, which both show
 * this text under the email field.
 */
export function EmailVerifiedText({ verifiedAt }: EmailVerifiedTextProps): JSX.Element {
  if (verifiedAt === null) {
    return <span>Unverified</span>;
  }
  return (
    <span>
      Verified <DateText value={verifiedAt} />
    </span>
  );
}
