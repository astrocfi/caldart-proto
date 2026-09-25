import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useRenewal, useSiteConfig } from '@/portal/api/queries';
import type { RenewalMandate } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { MembershipChip, PaymentChip, membershipTone } from '@/portal/components/StatusChip';
import { automaticCardTitle, automaticKindLabel } from '@/portal/features/payments/labels';
import { useMembership, useMyPayments } from '@/portal/features/profile/api';
import { groupedNavItems } from '@/portal/nav';
import './dashboard.css';

/** How many payments the dashboard shows before sending you elsewhere. */
const RECENT_PAYMENTS = 5;

/**
 * `/` — the member's home.
 *
 * Reading order is the order things matter: is my membership current, is my
 * profile usable, what can I read, what have I paid.  The renewal call to
 * action moves to the top and takes an accent edge inside 30 days.
 */
export function DashboardPage(): JSX.Element {
  const { user, roles } = useAuth();
  const membership = useMembership();
  const payments = useMyPayments();
  const renewal = useRenewal();
  const siteConfig = useSiteConfig();

  const status = membership.data ?? user?.membership ?? null;
  const tone = status ? membershipTone(status) : 'none';
  const urgent = tone === 'expiring' || tone === 'expired' || tone === 'none';
  const greeting = user?.first_name ? `Welcome, ${user.first_name}` : 'Welcome';

  const linkGroups = groupedNavItems(roles).map((bucket) => ({
    ...bucket,
    items: bucket.items.filter((item) => item.to !== '/'),
  }));

  const membersPages = siteConfig.data?.members_pages ?? [];
  const recent = (payments.data ?? []).slice(0, RECENT_PAYMENTS);

  return (
    <Page title={greeting} eyebrow="Member portal">
      <div className="grid">
        <div className="col-text stack-loose">
          <Card
            className={urgent ? 'dashboard__card--urgent' : undefined}
            eyebrow="Membership"
            title={<MembershipHeadline status={status} />}
          >
            {status ? (
              <div className="dashboard__status">
                <MembershipChip membership={status} />
                {status.is_lifetime && status.status === 'current' ? (
                  <p className="muted">Nothing to renew — thank you for joining for life.</p>
                ) : status.expires_on ? (
                  <p className="dashboard__expiry">
                    <span className="dashboard__expiry-label">
                      {status.status === 'current' ? 'Expires' : 'Expired'}
                    </span>
                    <DateText value={status.expires_on} />
                  </p>
                ) : null}
                {status.plan && !(status.is_lifetime && status.status === 'current') ? (
                  <p className="muted">{status.plan} membership</p>
                ) : null}
              </div>
            ) : (
              <p className="muted" role="status">
                Checking your membership…
              </p>
            )}

            {status && !(status.is_lifetime && status.status === 'current') ? (
              <div className="cluster card__footer">
                {status.status === 'none' ? (
                  <ButtonLink to="/join">Join CalDART</ButtonLink>
                ) : (
                  <ButtonLink to="/renew" variant={urgent ? 'primary' : 'secondary'}>
                    {status.status === 'expired' ? 'Renew now' : 'Renew'}
                  </ButtonLink>
                )}
                <Link to="/profile">Update your details</Link>
              </div>
            ) : null}
          </Card>

          {user && !user.profile_complete ? (
            <Card
              className="dashboard__nudge"
              eyebrow="Next step"
              title="Finish your profile"
              footer={<ButtonLink to="/profile">Complete my profile</ButtonLink>}
            >
              <p>
                We still need your phone number and address so a DART leader can reach you during an
                activation.
              </p>
            </Card>
          ) : null}

          <Card eyebrow="Members only" title="Member content">
            {siteConfig.isPending ? (
              <p className="muted" role="status">
                Loading…
              </p>
            ) : membersPages.length === 0 ? (
              <EmptyState
                title="Nothing published yet"
                description="Members-only pages will appear here as soon as CalDART publishes them."
              />
            ) : (
              <ul className="dashboard__links" role="list">
                {membersPages.map((page) => (
                  <li key={page.url}>
                    <a href={page.url}>{page.title}</a>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            eyebrow="History"
            title="Recent payments"
            footer={<Link to="/payments">All payments, receipts and renewal</Link>}
          >
            <RenewalLine
              mandate={renewal.data?.mandate ?? null}
              isLifetime={status?.is_lifetime ?? false}
            />
            {payments.isPending ? (
              <p className="muted" role="status">
                Loading…
              </p>
            ) : recent.length === 0 ? (
              <EmptyState
                title="No payments yet"
                description="Payments you make to CalDART will be listed here."
              />
            ) : (
              <div className="table-wrap">
                <table className="dashboard__payments">
                  <caption>Your most recent payments</caption>
                  <thead>
                    <tr>
                      <th scope="col">Date</th>
                      <th scope="col">Plan</th>
                      <th scope="col" className="numeric">
                        Amount
                      </th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((payment) => (
                      <tr key={payment.id}>
                        <td>
                          <DateText value={payment.completed_at} withTime />
                        </td>
                        <td>{payment.plan ?? 'Contribution'}</td>
                        <td className="numeric">
                          <Money cents={payment.amount_cents} />
                        </td>
                        <td>
                          <PaymentChip status={payment.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="col-side">
          <Card eyebrow="Go to" title="Quick links">
            {linkGroups.map((bucket) => (
              <div key={bucket.group} className="dashboard__link-group">
                <p className="eyebrow">{bucket.group}</p>
                <ul className="dashboard__links" role="list">
                  {bucket.items.map((item) => (
                    <li key={item.to}>
                      <Link to={item.to}>{item.label}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </Page>
  );
}

interface RenewalLineProps {
  mandate: RenewalMandate | null;
  /** True for a life member, whose authority is over their contribution alone. */
  isLifetime: boolean;
}

/** One line on the dashboard saying what CalDART will charge, and when. */
function RenewalLine({ mandate, isLifetime }: RenewalLineProps) {
  if (mandate === null || mandate.status === 'pending' || mandate.status === 'canceled') {
    return <p className="muted">{automaticCardTitle(isLifetime)} is off.</p>;
  }
  const authority = automaticKindLabel(mandate.kind);
  if (mandate.status === 'paused') {
    return (
      <p className="muted">
        {authority} stopped after a payment was refused. Save another method to start it again.
      </p>
    );
  }
  return (
    <p className="muted">
      {authority} is on: <Money cents={mandate.amount_cents} /> on{' '}
      <DateText value={mandate.next_charge_on} />.
    </p>
  );
}

function MembershipHeadline({
  status,
}: {
  status: { status: string; is_lifetime: boolean } | null;
}) {
  if (!status) return <>Your membership</>;
  if (status.status === 'current') {
    return <>{status.is_lifetime ? 'Lifetime member' : 'Your membership is current'}</>;
  }
  if (status.status === 'expired') return <>Your membership has expired</>;
  return <>You are not a member yet</>;
}
