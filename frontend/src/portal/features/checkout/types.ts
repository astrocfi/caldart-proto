/** Shapes shared by the checkout widget and its provider panels. */
import type { IsoDate, MandateCadence, MembershipStatus } from '@/portal/api/types';

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
  /**
   * A recurring donation was set up to start on a later day, so nothing was paid
   * today.  Handed the day of the first charge.
   */
  onScheduled?: (firstChargeOn: IsoDate) => void;
}

/** Every provider panel is handed the chosen plan and the running total. */
export interface ProviderPanelProps {
  /** Plan slug, or null for a contribution on its own. */
  plan: string | null;
  contributionCents: number;
  /** Plan price plus contribution, for display only — the server recomputes. */
  amountCents: number;
  /**
   * Save the method and charge it again: each year to renew a plan, or on `cadence`
   * for a recurring donation.
   */
  autoRenew: boolean;
  /** How often a recurring donation charges; left out for a renewal. */
  cadence?: MandateCadence;
  /** The member agreed to move their renewal's contribution to this donation. */
  removeRenewalContribution?: boolean;
  /**
   * The server refused the donation because the renewal takes a contribution;
   * handed the server's sentence.
   */
  onRenewalContribution?: (detail: string) => void;
  onSuccess: (result: CheckoutResult) => void;
}
