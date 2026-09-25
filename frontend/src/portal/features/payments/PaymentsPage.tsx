/**
 * `/payments` — everything a member needs to know about money they have paid
 * CalDART, and about money CalDART will take next.
 *
 * Reading order is the order things matter: what is about to happen, what has
 * happened, and what the member's accountant will ask for.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { useMembership, useMyPayments } from '@/portal/features/profile/api';
import { AutoRenewalCard } from './AutoRenewalCard';
import { paymentsPageLede } from './labels';
import { PaymentsTable } from './PaymentsTable';
import { StatementsCard } from './StatementsCard';
import './payments.css';

/** The member's own payments screen: renewal, history, statements. */
export function PaymentsPage(): JSX.Element {
  const payments = useMyPayments();
  const membership = useMembership();
  const isLifetime = membership.data?.is_lifetime ?? false;

  return (
    <Page title="Payments" eyebrow="Membership" lede={paymentsPageLede(isLifetime)}>
      <AutoRenewalCard />

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
