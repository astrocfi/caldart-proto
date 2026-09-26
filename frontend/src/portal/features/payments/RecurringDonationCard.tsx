/**
 * The Recurring donation card on the Payments screen.
 *
 * It is {@link MandateCard} over the donation, the same card the automatic renewal
 * uses: what is on, how much, how often, and when it next charges, with **Change**,
 * **Turn off**, and **Set up**, which goes to the Donate screen.
 */
import type { JSX } from 'react';

import { MandateCard } from './AutoRenewalCard';

/** The member's recurring donation, with the controls that change it. */
export function RecurringDonationCard(): JSX.Element {
  return <MandateCard scope="donation" />;
}
