/**
 * What a completed payment moves, in one place.
 *
 * A payment changes the membership term, the payment history and
 * `membership`/`profile_complete` on the user payload, and three screens have
 * to react to that: the wizard's pay step, the wizard's redirect landing pad
 * and `/renew`.  Keeping the key list here stops one of them being forgotten.
 */
import type { QueryClient } from '@tanstack/react-query';

import { AUTH_ME_KEY } from '../../auth/useAuth';
import { MEMBERSHIP_KEY, PAYMENTS_KEY } from '../profile/api';

export function refreshAfterPayment(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
  void queryClient.invalidateQueries({ queryKey: MEMBERSHIP_KEY });
  void queryClient.invalidateQueries({ queryKey: PAYMENTS_KEY });
}
