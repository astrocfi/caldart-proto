/**
 * Shared checkout widget.
 *
 * This is the *interface* `feat/profile-join` codes against; `feat/payments`
 * replaces the body with the Stripe Payment Element, the PayPal buttons and
 * the mock "Succeed / Fail" pair.  Do not change the props without telling
 * both branches.
 */
import type { JSX } from 'react';

import { Card } from '../../components/Card';
import type { MembershipStatus } from '../../api/types';

export interface CheckoutResult {
  paymentId: number;
  membership: MembershipStatus;
}

export interface CheckoutProps {
  mode: 'join' | 'renew';
  onSuccess: (result: CheckoutResult) => void;
}

export function Checkout(props: CheckoutProps): JSX.Element {
  return (
    <Card eyebrow={props.mode === 'renew' ? 'Renewal' : 'Membership'} title="Payment">
      <p className="muted">Payment coming soon</p>
    </Card>
  );
}
