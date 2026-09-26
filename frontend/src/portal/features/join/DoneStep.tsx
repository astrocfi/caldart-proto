/**
 * Step 5 — you are in: status card and the two places to go next.
 *
 * A member also sees the members-only pages they can now read.  A friend sees what
 * being a friend means instead, since those pages are for members.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useSiteConfig } from '@/portal/api/queries';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { MembershipChip } from '@/portal/components/StatusChip';
import { useMembership } from '@/portal/features/profile/api';
import { joinStepEyebrow } from './steps';
import './join.css';

/** Step 5 of the join wizard: membership status and links to members-only pages. */
export function DoneStep(): JSX.Element {
  const membership = useMembership();
  const siteConfig = useSiteConfig();
  const membersPages = siteConfig.data?.members_pages ?? [];
  const status = membership.data ?? null;
  const isFriend = status?.status === 'friend';

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
            <p className="muted">
              {isFriend ? 'If you made a contribution, a receipt' : 'A receipt'} is on its way to
              your inbox, with the PDF attached. You can download it again at any time from{' '}
              <Link to="/payments">Payments</Link>.
            </p>
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
