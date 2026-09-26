/**
 * `/donate` — give to CalDART once, or on a schedule.
 *
 * The page is the shared checkout in its contribution form: an amount, then
 * **Make this a recurring donation** with how often and the day of the first
 * charge.  A gift taken now, recurring or not, thanks the giver and goes to
 * Payments, where the recurring donation is shown; one set up for a later day
 * does the same without taking anything today.  Any member or friend may give,
 * whatever their membership.  Somebody who already gives on a schedule is told so
 * first, and pointed to Payments to change it: a recurring donation set up here
 * replaces theirs.
 */
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { DONATION_KEY, RENEWAL_KEY, useDonation } from '@/portal/api/queries';
import type { IsoDate, RenewalMandate } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { formatCents } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { Checkout } from '@/portal/features/checkout/Checkout';
import { refreshAfterPayment } from '@/portal/features/join/refresh';
import { CADENCE_PHRASES } from '@/portal/features/payments/labels';

/** Where a giver goes once the gift is made or scheduled. */
const AFTER_GIVING = '/payments';

/** The Donate screen: the checkout's contribution form, with a recurring option. */
export function DonatePage(): JSX.Element {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const held = useDonation().data?.mandate;

  function refresh(): void {
    refreshAfterPayment(queryClient);
    // A donation can take the contribution off the renewal as it starts, so both
    // standing authorities are read again.
    void queryClient.invalidateQueries({ queryKey: DONATION_KEY });
    void queryClient.invalidateQueries({ queryKey: RENEWAL_KEY });
  }

  function handleSuccess(): void {
    refresh();
    toast.show('Thank you for your donation.', 'success');
    void navigate(AFTER_GIVING);
  }

  function handleScheduled(firstChargeOn: IsoDate): void {
    refresh();
    toast.show(
      `Thank you. Your recurring donation starts on ${formatDate(firstChargeOn)}.`,
      'success',
    );
    void navigate(AFTER_GIVING);
  }

  return (
    <Page
      title="Donate"
      eyebrow="Membership"
      lede="Give once, or on a schedule. Every gift pays for training, fuel, and equipment."
    >
      {held?.status === 'active' ? <HeldDonation mandate={held} /> : null}
      <Checkout mode="contribute" onSuccess={handleSuccess} onScheduled={handleScheduled} />
    </Page>
  );
}

/** The recurring donation somebody already gives, and where to change it. */
function HeldDonation({ mandate }: { mandate: RenewalMandate }): JSX.Element {
  return (
    <Card
      eyebrow="Recurring donation"
      footer={
        <Link className="button button--secondary" to={AFTER_GIVING}>
          Go to Payments
        </Link>
      }
    >
      <p>
        You already give {formatCents(mandate.contribution_cents)}{' '}
        {CADENCE_PHRASES[mandate.cadence]} by recurring donation. To change it, press Change on
        Payments. A recurring donation set up here replaces it.
      </p>
    </Card>
  );
}
