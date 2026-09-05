/** Shapes shared by the checkout widget and its provider panels. */
import type { MembershipStatus } from '../../api/types';

/** What a completed checkout hands back to the join or renew flow. */
export interface CheckoutResult {
  paymentId: number;
  membership: MembershipStatus;
}

export interface CheckoutProps {
  mode: 'join' | 'renew';
  onSuccess: (result: CheckoutResult) => void;
}

/** Every provider panel is handed the chosen plan and the running total. */
export interface ProviderPanelProps {
  /** Plan slug, or null for a contribution on its own. */
  plan: string | null;
  contributionCents: number;
  /** Plan price plus contribution, for display only — the server recomputes. */
  amountCents: number;
  onSuccess: (result: CheckoutResult) => void;
}
