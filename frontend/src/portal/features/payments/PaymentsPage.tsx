/**
 * `/payments` — everything a member needs to know about money they have paid
 * CalDART, and about money CalDART will take next.
 *
 * Reading order is the order things matter: what is about to happen, what has
 * happened, and what the member's accountant will ask for.  Somebody with no
 * membership to renew -- a life member or a friend -- is not offered an automatic
 * renewal, though one they still hold stays on screen so they can turn it off;
 * everybody may give on a schedule.
 */
import type { JSX } from 'react';

import { useRenewal } from '@/portal/api/queries';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { useMembership, useMyPayments } from '@/portal/features/profile/api';
import { AutoRenewalCard } from './AutoRenewalCard';
import { paymentsPageLede } from './labels';
import { PaymentsTable } from './PaymentsTable';
import { RecurringDonationCard } from './RecurringDonationCard';
import { StatementsCard } from './StatementsCard';
import './payments.css';

/** The member's own payments screen: renewal, donation, history, statements. */
export function PaymentsPage(): JSX.Element {
  const payments = useMyPayments();
  const membership = useMembership();
  const renewal = useRenewal();
  // Until the membership is known the card stays, as it does for a member whose
  // membership cannot be read: hiding it would take their own controls away.
  const renews =
    membership.data === undefined ||
    (!membership.data.is_lifetime && membership.data.status !== 'friend');
  const held = renewal.data?.mandate;
  const holdsRenewal = held !== null && held !== undefined && held.status !== 'canceled';
  const showsRenewal = renews || holdsRenewal;

  return (
    <Page title="Payments" eyebrow="Membership" lede={paymentsPageLede(showsRenewal)}>
      {showsRenewal ? <AutoRenewalCard /> : null}
      <RecurringDonationCard />

      <Card eyebrow="History" title="Your payments">
        {payments.isPending ? (
          <p className="muted" role="status">
            Loading…
          </p>
        ) : payments.error ? (
          <EmptyState
            title="Your payments could not be loaded"
            description="Please reload the page, or contact CalDART if it keeps happening."
          />
        ) : (
          <PaymentsTable payments={payments.data ?? []} />
        )}
      </Card>

      <StatementsCard />
    </Page>
  );
}
