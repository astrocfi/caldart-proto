/** Shapes shared by the standing-authority setup flow and its provider panels. */
import type { IsoDate, MandateCadence, MandateProvider } from '@/portal/api/types';
import type { MandateScope } from '@/portal/api/queries';

/** Every setup panel is handed what the member chose, and which authority it is. */
export interface RenewalPanelProps {
  /** The automatic renewal or the recurring donation. */
  scope: MandateScope;
  /**
   * The slug of the plan that will renew; never a plan that lasts for life, and
   * null for a recurring donation, which renews nothing.
   */
  plan: string | null;
  contributionCents: number;
  /** The day the saved method is first charged on, as the member chose it. */
  nextChargeOn: IsoDate;
  /** How often a recurring donation charges; left out for a renewal. */
  cadence?: MandateCadence;
  /** The member agreed to move their renewal's contribution to this donation. */
  removeRenewalContribution?: boolean;
  /**
   * The server refused the donation because the renewal takes a contribution;
   * handed the server's sentence.
   */
  onRenewalContribution?: (detail: string) => void;
  /** Called once the mandate is active. */
  onDone: () => void;
}

/** Tab order for the setup flow, so it does not follow the server's ordering. */
export const MANDATE_PROVIDER_ORDER: MandateProvider[] = ['stripe', 'paypal', 'mock'];

/** What each tab in the setup flow is called. */
export const MANDATE_PROVIDER_LABELS: Record<MandateProvider, string> = {
  stripe: 'Card',
  paypal: 'PayPal',
  mock: 'Test payment method',
};
