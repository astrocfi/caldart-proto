/** Shapes shared by the automatic-renewal setup flow and its provider panels. */
import type { MandateProvider } from '@/portal/api/types';

/** Every setup panel is handed the plan and contribution the member chose. */
export interface RenewalPanelProps {
  /**
   * The slug of the plan that will renew; never a plan that lasts for life, and
   * null for a life member, whose authority is over the contribution alone.
   */
  plan: string | null;
  contributionCents: number;
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
