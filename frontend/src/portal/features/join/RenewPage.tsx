/**
 * `/renew` — renew an existing membership.
 *
 * The new term starts the day after the current one ends, so renewing early
 * costs nothing; the status card above the checkout says exactly what the
 * member has now, at the checkout's own width.  A life member has nothing to renew and
 * gives through Donate like everyone else, so the page sends them to `/donate`.  A
 * friend has no membership to renew either (that includes a member who registered and
 * has not yet paid), so the page sends them on to `/membership/join`.
 */
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';

import { Checkout } from '@/portal/features/checkout';

import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { MembershipDot, daysUntil } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { JOIN_AS_MEMBER_PATH } from '@/portal/features/dashboard/KindSwitch';
import { useMembership } from '@/portal/features/profile/api';
import { refreshAfterPayment } from './refresh';
import './join.css';

/** Where a life member gives, having no term to renew. */
export const LIFETIME_GIVING_PATH = '/donate';

/** Renders the current membership status and a checkout to renew it. */
export function RenewPage(): JSX.Element {
  const membership = useMembership();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const status = membership.data ?? null;
  const days = status ? daysUntil(status.expires_on) : null;

  if (status?.status === 'friend') {
    return <Navigate to={JOIN_AS_MEMBER_PATH} replace />;
  }
  if (status?.is_lifetime === true) {
    return <Navigate to={LIFETIME_GIVING_PATH} replace />;
  }

  function handleSuccess() {
    refreshAfterPayment(queryClient);
    toast.show('Thank you — your membership is renewed.', 'success');
    void navigate('/');
  }

  return (
    <Page
      title="Renew your membership"
      lede="A renewal starts the day after your current term ends, so there is no penalty for renewing early."
    >
      <Card eyebrow="Now" title="Your membership">
        {membership.isPending ? (
          <p className="muted" role="status">
            Checking your membership…
          </p>
        ) : status ? (
          <div className="renew__status">
            <MembershipDot membership={status} />
            {status.expires_on ? (
              <p>
                {status.status === 'current' ? 'Expires ' : 'Expired '}
                <DateText value={status.expires_on} />
                {days !== null && status.status === 'current' ? (
                  <span className="muted">
                    {' '}
                    · {days} day{days === 1 ? '' : 's'} to go
                  </span>
                ) : null}
              </p>
            ) : null}
            {status.plan ? <p className="muted">{status.plan} membership</p> : null}
          </div>
        ) : null}
      </Card>

      <Checkout mode="renew" onSuccess={handleSuccess} />
    </Page>
  );
}
