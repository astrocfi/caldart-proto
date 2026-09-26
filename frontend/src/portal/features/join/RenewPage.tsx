/**
 * `/renew` — renew an existing membership, or contribute as a life member.
 *
 * The new term starts the day after the current one ends, so renewing early
 * costs nothing; the status card above the checkout says exactly what the
 * member has now.  A life member has nothing to renew, so the page asks for a
 * contribution instead.
 */
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { Checkout } from '@/portal/features/checkout';

import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { MembershipChip, daysUntil } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { useMembership } from '@/portal/features/profile/api';
import { refreshAfterPayment } from './refresh';
import './join.css';

/** Renders the current membership status and a checkout to renew it. */
export function RenewPage(): JSX.Element {
  const membership = useMembership();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const status = membership.data ?? null;
  const days = status ? daysUntil(status.expires_on) : null;

  const isLifetime = status?.is_lifetime ?? false;

  function handleSuccess() {
    refreshAfterPayment(queryClient);
    toast.show(
      isLifetime ? 'Thank you for your contribution.' : 'Thank you — your membership is renewed.',
      'success',
    );
    void navigate('/');
  }

  return (
    <div className="join-shell">
      <Page
        title={isLifetime ? 'Contribute to CalDART' : 'Renew your membership'}
        eyebrow="Membership"
        lede={
          isLifetime
            ? 'As a life member you have nothing to renew. A contribution keeps the DARTs flying.'
            : 'A renewal starts the day after your current term ends, so there is no penalty for renewing early.'
        }
      >
        <Card eyebrow="Now" title="Where you stand" className="join-card">
          {membership.isPending ? (
            <p className="muted" role="status">
              Checking your membership…
            </p>
          ) : status ? (
            <div className="renew__status">
              <MembershipChip membership={status} />
              {status.is_lifetime ? (
                <p>You are a life member. Thank you.</p>
              ) : status.expires_on ? (
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
              ) : (
                <p>You have never held a CalDART membership.</p>
              )}
              {status.plan && !status.is_lifetime ? (
                <p className="muted">{status.plan} membership</p>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Checkout mode={isLifetime ? 'contribute' : 'renew'} onSuccess={handleSuccess} />
      </Page>
    </div>
  );
}
