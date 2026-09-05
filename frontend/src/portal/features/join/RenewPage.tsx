/**
 * `/renew` — renew an existing membership (PLAN §8, §10).
 *
 * The new term starts the day after the current one ends, so renewing early
 * costs nothing; the status card above the checkout says exactly what the
 * member has now.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { Checkout } from '@/portal/features/checkout';

import { AUTH_ME_KEY } from '../../auth/useAuth';
import { Card } from '../../components/Card';
import { DateText } from '../../components/DateText';
import { Page } from '../../components/Page';
import { MembershipChip, daysUntil } from '../../components/StatusChip';
import { useToast } from '../../components/Toast';
import { MEMBERSHIP_KEY, PAYMENTS_KEY, useMembership } from '../profile/api';
import './join.css';

export function RenewPage() {
  const membership = useMembership();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const status = membership.data ?? null;
  const days = status ? daysUntil(status.expires_on) : null;

  function handleSuccess() {
    void queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    void queryClient.invalidateQueries({ queryKey: MEMBERSHIP_KEY });
    void queryClient.invalidateQueries({ queryKey: PAYMENTS_KEY });
    toast.show('Thank you — your membership is renewed.', 'success');
    navigate('/');
  }

  return (
    <Page
      title="Renew your membership"
      eyebrow="Membership"
      lede="A renewal starts the day after your current term ends, so there is no penalty for renewing early."
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
              <p>You are a life member — there is nothing to renew.</p>
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
            {status.plan ? <p className="muted">{status.plan} membership</p> : null}
          </div>
        ) : null}
      </Card>

      <Checkout mode="renew" onSuccess={handleSuccess} />
    </Page>
  );
}
