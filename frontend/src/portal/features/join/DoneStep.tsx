/** Step 4 — you are in: status card and the two places to go next. */
import { ButtonLink } from '../../components/Button';
import { Card } from '../../components/Card';
import { DateText } from '../../components/DateText';
import { EmptyState } from '../../components/EmptyState';
import { MembershipChip } from '../../components/StatusChip';
import { useMembership, useSiteConfig } from '../profile/api';
import './join.css';

export function DoneStep() {
  const membership = useMembership();
  const siteConfig = useSiteConfig();
  const membersPages = siteConfig.data?.members_pages ?? [];
  const status = membership.data ?? null;

  return (
    <>
      <Card
        className="join-card"
        eyebrow="Step 4 of 4"
        title={status?.status === 'current' ? 'Welcome to CalDART' : 'Almost there'}
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
            {status.is_lifetime ? (
              <p>You are a life member. There is nothing more to pay, ever.</p>
            ) : status.expires_on ? (
              <p>
                Your membership runs until <DateText value={status.expires_on} />. We will email you
                before it expires.
              </p>
            ) : (
              <p>Your membership is not active yet.</p>
            )}
          </div>
        ) : null}
      </Card>

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
    </>
  );
}
