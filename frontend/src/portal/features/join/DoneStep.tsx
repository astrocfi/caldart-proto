/**
 * Step 5 — you are in: status card and the two places to go next.
 *
 * A member also sees the members-only pages they can now read.  A friend sees what
 * being a friend means instead, since those pages are for members.  The receipt is
 * mentioned only after a payment in this visit: a friend who skipped paying, or a
 * member who signed in and was sent here, has none coming.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useSiteConfig } from '@/portal/api/queries';
import { useAuth } from '@/portal/auth/useAuth';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { MembershipChip } from '@/portal/components/StatusChip';
import { useMembership } from '@/portal/features/profile/api';
import { joinStepEyebrow, joiningAs } from './steps';
import './join.css';

export interface DoneStepProps {
  /** True when a payment settled in this visit, so a receipt is on its way. */
  hasPaid: boolean;
}

/** Step 5 of the join wizard: membership status and links to members-only pages. */
export function DoneStep({ hasPaid }: DoneStepProps): JSX.Element {
  const { user } = useAuth();
  const membership = useMembership();
  const siteConfig = useSiteConfig();
  const membersPages = siteConfig.data?.members_pages ?? [];
  const status = membership.data ?? null;
  // The stored intent, not the membership: a member whose payment has not settled
  // still reads as a friend, and is told their membership is on its way.
  const isFriend = joiningAs(user) === 'friend';

  return (
    <>
      <Card
        className="join-card"
        eyebrow={joinStepEyebrow('done')}
        title={status?.status === 'current' || isFriend ? 'Welcome to CalDART' : 'Almost there'}
        footer={
          <>
            <ButtonLink to="/">Go to my dashboard</ButtonLink>
            <ButtonLink to="/profile/aircraft" variant="secondary">
              Add the planes I fly
            </ButtonLink>
          </>
        }
      >
        {membership.isPending ? (
          <p className="muted" role="status">
            Checking your membership…
          </p>
        ) : status ? (
          <div className="renew__status">
            <MembershipChip membership={status} />
            {isFriend ? (
              <p>You are a friend of CalDART: no dues, no expiry. Become a member any time.</p>
            ) : status.is_lifetime ? (
              <p>You are a life member. There is nothing more to pay, ever.</p>
            ) : status.expires_on ? (
              <p>
                Your membership runs until <DateText value={status.expires_on} />. We will email you
                before it expires.
              </p>
            ) : (
              <p>Your membership is not active yet.</p>
            )}
            {hasPaid ? (
              <p className="muted">
                A receipt is on its way to your inbox, with the PDF attached. You can download it
                again at any time from <Link to="/payments">Payments</Link>.
              </p>
            ) : null}
          </div>
        ) : null}
      </Card>

      {isFriend ? null : (
        <Card eyebrow="Members only" title="What you can read now" className="join-card">
          {siteConfig.isPending ? (
            <p className="muted" role="status">
              Loading…
            </p>
          ) : membersPages.length === 0 ? (
            <EmptyState
              title="Nothing published yet"
              description="Members-only pages appear here as soon as CalDART publishes them."
            />
          ) : (
            <ul className="join-done__list" role="list">
              {membersPages.map((page) => (
                <li key={page.url}>
                  <a href={page.url}>{page.title}</a>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  );
}
