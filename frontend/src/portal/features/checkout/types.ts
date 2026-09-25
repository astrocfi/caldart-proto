/** Shapes shared by the checkout widget and its provider panels. */
import type { MembershipStatus } from '@/portal/api/types';

/** What a completed checkout hands back to the join or renew flow. */
export interface CheckoutResult {
  paymentId: number;
  membership: MembershipStatus;
}

/** What the checkout is for: a first term, a renewal, or a contribution alone. */
export type CheckoutMode = 'join' | 'renew' | 'contribute';

export interface CheckoutProps {
  mode: CheckoutMode;
  onSuccess: (result: CheckoutResult) => void;
}

/** Every provider panel is handed the chosen plan and the running total. */
export interface ProviderPanelProps {
  /** Plan slug, or null for a contribution on its own. */
  plan: string | null;
  contributionCents: number;
  /** Plan price plus contribution, for display only — the server recomputes. */
  amountCents: number;
  /** Save the method and renew the membership from it each year. */
  autoRenew: boolean;
  onSuccess: (result: CheckoutResult) => void;
}
