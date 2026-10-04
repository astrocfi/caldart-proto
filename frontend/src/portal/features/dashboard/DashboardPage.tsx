import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useDonation, useRenewal, useSiteConfig } from '@/portal/api/queries';
import type { MembershipStatus, PaymentSummary, RenewalMandate } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { MembershipDot, PaymentDot, membershipTone } from '@/portal/components/StatusDot';
import { automaticCardTitle, automaticKindLabel } from '@/portal/features/payments/labels';
import { useMembership, useMyPayments } from '@/portal/features/profile/api';
import { groupedNavItems } from '@/portal/nav';
import { KindSwitch } from './KindSwitch';
import './dashboard.css';

/** How many payments the dashboard shows before sending you elsewhere. */
const RECENT_PAYMENTS = 5;

/**
 * The recent payments' columns.  The date identifies a payment, never gives way, and
 * stays pinned when the table scrolls; the amount and the status stay in sight on a
 * phone, where the plan gives way first.
 */
const RECENT_PAYMENT_COLUMNS: Column<PaymentSummary>[] = [
  {
    key: 'date',
    header: 'Date',
    width: '9.5rem',
    isIdentity: true,
    render: (payment) => <DateText value={payment.paid_on ?? payment.completed_at} />,
  },
  {
    key: 'plan',
    header: 'Plan',
    minWidth: '6rem',
    dropOrder: 1,
    render: (payment) => payment.plan ?? 'Contribution',
  },
  {
    key: 'amount',
    header: 'Amount',
    width: '6rem',
    numeric: true,
    keepInSight: true,
    render: (payment) => <Money cents={payment.amount_cents} />,
  },
  {
    key: 'status',
    header: 'Status',
    width: '9rem',
    narrowWidth: '7rem',
    keepInSight: true,
    render: (payment) => <PaymentDot status={payment.status} />,
  },
];

/**
 * `/` — the member's home.
 *
 * Reading order is the order things matter: is my membership current, what can I
 * read, what have I paid.  Nobody reaches it before the join wizard is finished (an
 * unverified address, an incomplete profile, and an unpaid member are all held
 * there), so it never asks for any of those.  The renewal call to action takes an
 * accent edge inside 30 days.  A friend's
 * membership card says what being a friend means and offers membership instead
 * of a renewal; a member's (not a life member's) offers **Make me a friend** beside
 * the renewal, or shows the day a change they asked for takes effect.
 */
export function DashboardPage(): JSX.Element {
  const { user, roles } = useAuth();
  const membership = useMembership();
  const payments = useMyPayments();
  const renewal = useRenewal();
  // A life member renews nothing, so the authority their line states is their
  // recurring donation.
  const donation = useDonation();
  const siteConfig = useSiteConfig();

  const status = membership.data ?? user?.membership ?? null;
  const tone = status ? membershipTone(status) : null;
  // A friend owes nothing, so their card never takes the urgent edge.  A member who
  // registered and has not yet paid reads as a friend, and gets the friend's card.
  const isFriend = status?.status === 'friend';
  const urgent = !isFriend && (tone === 'expiring' || tone === 'expired');
  // The members-only pages answer a friend with the wall unless a staff role lets
  // them read, so the card is not offered to a friend who would be refused.
  const isWalledOut = isFriend && roles.every((slug) => slug === 'member');
  const greeting = user?.first_name ? `Welcome, ${user.first_name}` : 'Welcome';

  const linkGroups = groupedNavItems(roles, {
    isEffectiveFriend: isFriend,
    isLifetime: status?.is_lifetime === true,
  }).map((bucket) => ({
    ...bucket,
    items: bucket.items.filter((item) => item.to !== '/'),
  }));

  const membersPages = siteConfig.data?.members_pages ?? [];
  const recent = (payments.data ?? []).slice(0, RECENT_PAYMENTS);

  return (
    <Page title={greeting} tabTitle="Dashboard">
      <div className="grid">
        <div className="col-text stack-loose">
          <Card
            className={urgent ? 'dashboard__card--urgent' : undefined}
            eyebrow={isFriend ? 'Friend of CalDART' : undefined}
            title={<MembershipHeadline status={status} />}
          >
            {isFriend ? (
              <FriendStatus />
            ) : status ? (
              <div className="dashboard__status">
                <MembershipDot membership={status} />
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

            {status && !isFriend && !(status.is_lifetime && status.status === 'current') ? (
              <div className="cluster card__footer">
                <ButtonLink to="/renew" variant={urgent ? 'primary' : 'secondary'}>
                  {status.status === 'expired' ? 'Renew now' : 'Renew'}
                </ButtonLink>
                <KindSwitch />
                <Link to="/profile">Update your details</Link>
              </div>
            ) : null}
          </Card>

          {isWalledOut ? null : (
            <Card eyebrow="Members only" title="Member content">
              {siteConfig.isPending ? (
                <p className="muted" role="status">
                  Loading…
                </p>
              ) : membersPages.length === 0 && status?.status === 'expired' ? (
                <p>
                  Members-only pages are open to current members.{' '}
                  <Link to="/renew">Renew to read them again.</Link>
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
          )}

          <Card
            eyebrow="History"
            title="Recent payments"
            footer={<Link to="/payments">All payments, receipts, and renewals</Link>}
          >
            <RenewalLine
              mandate={(status?.is_lifetime ? donation : renewal).data?.mandate ?? null}
              isLifetime={status?.is_lifetime ?? false}
            />
            <DataTable
              singleLine
              columns={RECENT_PAYMENT_COLUMNS}
              rows={recent}
              rowKey={(payment) => payment.id}
              caption="Your most recent payments"
              isLoading={payments.isPending}
              emptyTitle="No payments yet"
              emptyDescription="Payments you make to CalDART will be listed here."
            />
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

/** A friend's membership card: what being one means, and the way to membership. */
function FriendStatus() {
  return (
    <>
      <div className="dashboard__status">
        <p>You are a friend of CalDART: no dues, no expiry. Become a member any time.</p>
      </div>
      <div className="cluster card__footer">
        <ButtonLink to="/membership/join" variant="secondary">
          Make me a member
        </ButtonLink>
        <Link to="/profile">Update your details</Link>
      </div>
    </>
  );
}

/** The membership card's title: current, expired, or a friend of CalDART. */
function MembershipHeadline({
  status,
}: {
  status: Pick<MembershipStatus, 'status' | 'is_lifetime'> | null;
}) {
  if (!status) return <>Your membership</>;
  if (status.status === 'current') {
    return <>{status.is_lifetime ? 'Lifetime member' : 'Your membership is current'}</>;
  }
  if (status.status === 'expired') return <>Your membership has expired</>;
  return <>You are a friend of CalDART</>;
}
