import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useDonation, useRenewal, useSiteConfig } from '@/portal/api/queries';
import type {
  MembershipStatus,
  PaymentSummary,
  RenewalMandate,
  RoleSlug,
} from '@/portal/api/types';
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
import { OwnSenderNotice } from '@/portal/features/bulk-email/SenderNotice';
import { automaticCardTitle } from '@/portal/features/payments/labels';
import { purchaseLabel } from '@/portal/features/payments/PaymentsTable';
import { useMembership, useMyPayments } from '@/portal/features/profile/api';
import { hasAnyRole, visibleNavItems } from '@/portal/nav';
import type { NavItem, NavReader } from '@/portal/nav';
import { KindSwitch } from './KindSwitch';
import './dashboard.css';

/** How many payments the dashboard shows before sending you elsewhere. */
const RECENT_PAYMENTS = 5;

/** The most quick links the dashboard offers: a few next steps, not a copy of the menu. */
const MAX_QUICK_LINKS = 5;

/** The member's own next steps, after the way to pay (Renew, or Donate), in order. */
const MEMBER_LINKS = ['/profile', '/profile/aircraft', '/messages'];

/** A role's own task, and the roles that bring it to the dashboard. */
const ROLE_LINKS: { to: string; roles: RoleSlug[] }[] = [
  { to: '/leader', roles: ['dart_leader', 'account_admin', 'user_admin', 'verifier'] },
  { to: '/admin/payments', roles: ['account_admin', 'treasurer'] },
  { to: '/admin/members', roles: ['account_admin'] },
];

/**
 * The dashboard's quick links for a reader with `roles`: three to five next steps
 * rather than the whole menu.
 *
 * Every reader gets the way to pay, which is **Renew** for a member with a term to
 * renew and **Donate** for a friend or a life member, then **My profile**, **My
 * aircraft**, and **Messages**.  A role adds its own task: **Member check** for a DART
 * leader, a verifier, or an administrator; **Finance** for a treasurer or an account
 * administrator; **Members** for an account administrator.  The role's tasks are kept
 * and the member's own links give way from the end, so the list never runs past five.
 * Each link takes its label from the menu.
 */
export function quickLinks(roles: readonly RoleSlug[], reader: NavReader): NavItem[] {
  const visible = visibleNavItems(roles, reader);
  const byPath = (to: string): NavItem | undefined => visible.find((item) => item.to === to);
  const pay = byPath('/renew') ?? byPath('/donate');
  const own = [pay, ...MEMBER_LINKS.map(byPath)].filter((item) => item !== undefined);
  const tasks = ROLE_LINKS.filter((link) => hasAnyRole(roles, link.roles))
    .map((link) => byPath(link.to))
    .filter((item) => item !== undefined);
  return [...own.slice(0, MAX_QUICK_LINKS - tasks.length), ...tasks];
}

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
    key: 'for',
    header: 'For',
    // Room for the longest name, "Annual and contribution", so it never reads cut off
    // while the fixed columns beside it have room to spare.
    minWidth: '12.5rem',
    dropOrder: 1,
    // Named as Payments names it: Annual, Annual and contribution, or Donation.
    render: (payment) => purchaseLabel(payment),
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
 * unverified address, an incomplete profile, and an unpaid joiner are all held
 * there), so it never asks for any of those.  An account an administrator created
 * reaches it before paying, and its card reads *You have no membership yet* with **Pay
 * dues**.  The renewal call to action takes an accent edge inside 30 days.  A friend's
 * membership card says what being a friend means and offers membership instead
 * of a renewal.  A member's card leads with **Renew**; becoming a friend is offered on
 * My profile alone, so a downgrade never sits beside the renewal, but a change the
 * member already asked for shows here with its day and **Undo**.  The quick links are a
 * few next steps for the reader's roles (`quickLinks`), not a copy of the menu.
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
  // A friend owes nothing, so their card never takes the urgent edge.  A member who has
  // not paid their first dues (`none`) has nothing to renew either, and is offered the
  // dues instead.
  const isFriend = status?.status === 'friend';
  const isAwaitingDues = status?.status === 'none';
  const isWithoutRenewal = isFriend || isAwaitingDues;
  const urgent = !isWithoutRenewal && (tone === 'expiring' || tone === 'expired');
  // The members-only pages answer anybody without a membership with the wall unless a
  // staff role lets them read, so the card is not offered to somebody who would be refused.
  const isWalledOut = isWithoutRenewal && roles.every((slug) => slug === 'member');
  const greeting = user?.first_name ? `Welcome, ${user.first_name}` : 'Welcome';

  const links = quickLinks(roles, {
    isEffectiveFriend: isWithoutRenewal,
    isLifetime: status?.is_lifetime === true,
  });
  // A friend and a life member renew nothing, so the authority their line states is
  // their recurring donation.
  const givesOnly = isWithoutRenewal || status?.is_lifetime === true;
  // Only a member with a term to renew has renewals among their payments.
  const hasRenewals = !givesOnly;

  const membersPages = siteConfig.data?.members_pages ?? [];
  const recent = (payments.data ?? []).slice(0, RECENT_PAYMENTS);

  return (
    <Page title={greeting} tabTitle="Dashboard">
      <OwnSenderNotice />
      <div className="grid">
        <div className="col-text dashboard__main stack-loose">
          <Card
            className={urgent ? 'dashboard__card--urgent' : undefined}
            eyebrow={isFriend ? 'Friend of CalDART' : undefined}
            title={<MembershipHeadline status={status} />}
          >
            {isFriend ? (
              <FriendStatus />
            ) : isAwaitingDues ? (
              <AwaitingDuesStatus />
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

            {status && !isWithoutRenewal && !(status.is_lifetime && status.status === 'current') ? (
              <div className="cluster card__footer">
                <ButtonLink to="/renew" variant={urgent ? 'primary' : 'secondary'}>
                  {status.status === 'expired' ? 'Renew now' : 'Renew'}
                </ButtonLink>
                {user?.friend_on ? <KindSwitch /> : null}
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
            footer={
              <Link to="/payments">
                {hasRenewals ? 'All payments, receipts, and renewals' : 'All payments and receipts'}
              </Link>
            }
          >
            <RenewalLine
              mandate={(givesOnly ? donation : renewal).data?.mandate ?? null}
              givesOnly={givesOnly}
              isFriend={isWithoutRenewal}
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
            <ul className="dashboard__links" role="list">
              {links.map((item) => (
                <li key={item.to}>
                  <Link to={item.to}>{item.label}</Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </Page>
  );
}

interface RenewalLineProps {
  mandate: RenewalMandate | null;
  /** True for a friend or a life member, whose authority is a recurring donation. */
  givesOnly: boolean;
  /** True for a friend, who is told nothing about an authority they do not hold. */
  isFriend: boolean;
}

/**
 * One line on the dashboard saying what CalDART will charge, and when: "Automatic
 * renewal is on: $145.00 will be charged on 04/27/2027.", or the recurring donation's
 * for a friend or a life member.  A friend with no recurring donation gets no line,
 * since a friend has nothing to renew.
 */
function RenewalLine({ mandate, givesOnly, isFriend }: RenewalLineProps) {
  const authority = automaticCardTitle(givesOnly);
  if (mandate === null || mandate.status === 'pending' || mandate.status === 'canceled') {
    return isFriend ? null : <p className="muted">{authority} is off.</p>;
  }
  if (mandate.status === 'paused') {
    return (
      <p className="muted">
        {authority} stopped after a payment was refused. Save another method to start it again.
      </p>
    );
  }
  return (
    <p className="muted">
      {authority} is on: <Money cents={mandate.amount_cents} /> will be charged on{' '}
      <DateText value={mandate.next_charge_on} />.
    </p>
  );
}

/** A friend's membership card: what being one means, and the way to membership. */
function FriendStatus() {
  return (
    <>
      <div className="dashboard__status">
        <p>No dues and no expiry. Become a member any time.</p>
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

/** A member who has not paid: what is missing, and the way to pay. */
function AwaitingDuesStatus() {
  return (
    <>
      <div className="dashboard__status">
        <p>Pay your dues to become a member of CalDART.</p>
      </div>
      <div className="cluster card__footer">
        <ButtonLink to="/membership/join">Pay dues</ButtonLink>
        <Link to="/profile">Update your details</Link>
      </div>
    </>
  );
}

/** The membership card's title: current, expired, not yet paid, or a friend of CalDART. */
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
  if (status.status === 'none') return <>You have no membership yet</>;
  return <>You are a friend of CalDART</>;
}
