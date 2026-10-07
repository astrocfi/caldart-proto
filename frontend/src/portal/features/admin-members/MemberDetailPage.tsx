/**
 * `/admin/members/:id` — one member record, in four tabs.
 *
 * The summary strip above the tabs says where the membership stands in words: a member
 * with no term in force is pointed at Memberships, and one whose terms a deactivation
 * set aside says so, rather than either reading as a friend.
 *
 * A donor's record is reached from the donors report rather than the member list,
 * and leads back to it for a reader who opens that report (see `recordHome`).
 *
 * The tab is held in the query string so a colleague can be sent straight to
 * the memberships table, and the tab strip follows the WAI-ARIA tabs pattern:
 * arrow keys move between tabs, Home and End jump to the ends.
 */
import { useRef } from 'react';
import type { JSX } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import type { MemberDetail } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { ACCOUNT_KIND_LABELS, roleLabel } from '@/portal/choices';
import { BouncedDot } from '@/portal/components/BouncedDot';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useTabBar } from '@/portal/components/useTabBar';
import { MemberDangerZone } from './MemberDangerZone';
import { MembershipSummary, factsFromTerms } from './MembershipSummary';
import { MemberEmailPreferences, showsEmailPreferences } from './MemberEmailPreferences';
import { MemberMembershipsTab } from './MemberMembershipsTab';
import { MemberPaymentsTab } from './MemberPaymentsTab';
import { MemberProfileTab } from './MemberProfileTab';
import { useMember } from './api';
import { recordHome } from './recordHome';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'memberships', label: 'Memberships' },
  { id: 'payments', label: 'Payments' },
  { id: 'danger', label: 'Delete or deactivate' },
] as const;

type TabId = (typeof TABS)[number]['id'];

function isTabId(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value);
}

interface TabsProps {
  active: TabId;
  onSelect: (id: TabId) => void;
}

/** The tab `index` positions away, wrapping round in both directions. */
function tabAt(index: number): TabId {
  const wrapped = ((index % TABS.length) + TABS.length) % TABS.length;
  return TABS[wrapped]?.id ?? 'profile';
}

function Tabs({ active, onSelect }: TabsProps) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const go = (id: TabId) => {
    onSelect(id);
    refs.current[id]?.focus();
  };

  const bar = useTabBar<HTMLDivElement>(active);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    const index = TABS.findIndex((tab) => tab.id === active);
    if (event.key === 'ArrowRight') go(tabAt(index + 1));
    else if (event.key === 'ArrowLeft') go(tabAt(index - 1));
    else if (event.key === 'Home') go(tabAt(0));
    else if (event.key === 'End') go(tabAt(TABS.length - 1));
    else return;
    event.preventDefault();
  };

  return (
    <div
      ref={bar.ref}
      className="tab-bar"
      role="tablist"
      aria-label="Member record sections"
      {...bar.attributes}
    >
      {TABS.map((tab) => (
        <button
          key={tab.id}
          ref={(node) => {
            refs.current[tab.id] = node;
          }}
          type="button"
          role="tab"
          id={`tab-${tab.id}`}
          aria-selected={active === tab.id}
          aria-controls={`panel-${tab.id}`}
          tabIndex={active === tab.id ? 0 : -1}
          className="tab-bar__tab"
          onClick={() => onSelect(tab.id)}
          onKeyDown={handleKeyDown}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function TabPanel({
  id,
  active,
  children,
}: {
  id: TabId;
  active: TabId;
  children: React.ReactNode;
}) {
  return (
    <div
      role="tabpanel"
      className="stack-loose"
      id={`panel-${id}`}
      aria-labelledby={`tab-${id}`}
      hidden={active !== id}
      tabIndex={0}
    >
      {active === id ? children : null}
    </div>
  );
}

/** The record's summary strip: the membership, the joining date, and the account's state. */
function MemberHeader({ member }: { member: MemberDetail }) {
  return (
    <Card>
      <div className="cluster">
        <MembershipSummary facts={factsFromTerms(member, member.memberships)} grantHint />
        {member.joined_on === null ? null : (
          <span className="muted">
            joined <DateText value={member.joined_on} />
          </span>
        )}
        <span className="muted">
          {member.profile_updated_at === null ? (
            'Profile never edited'
          ) : (
            <>
              Profile updated <DateText value={member.profile_updated_at} />
            </>
          )}
        </span>
        {member.kind === 'donor' ? <span>{ACCOUNT_KIND_LABELS.donor}</span> : null}
        {member.is_active ? null : <StatusDot tone="expired" label="Account deactivated" />}
      </div>
      <p className="muted cluster">
        <span>
          <a href={`mailto:${member.email}`}>{member.email}</a> ·{' '}
          {member.roles.map(roleLabel).join(', ')}
        </span>
        <BouncedDot bouncedAt={member.email_bounced_at} detail={member.email_bounce_detail} />
      </p>
    </Card>
  );
}

/** `/admin/members/:id` page: a member's profile, memberships, and payments tabs. */
export function MemberDetailPage(): JSX.Element {
  const { id } = useParams();
  const memberId = Number(id);
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const active: TabId = isTabId(requested) ? requested : 'profile';

  const member = useMember(Number.isFinite(memberId) ? memberId : null);
  const { roles } = useAuth();

  const handleSelectTab = (tab: TabId) => {
    const next = new URLSearchParams(params);
    if (tab === 'profile') next.delete('tab');
    else next.set('tab', tab);
    setParams(next, { replace: true });
  };

  if (member.isPending) {
    return (
      <Page title="Member">
        <p role="status">Loading…</p>
      </Page>
    );
  }

  if (member.isError || !member.data) {
    return (
      <Page title="Member">
        <EmptyState
          title="That member didn't load"
          description="They may have been deleted."
          action={<Link to="/admin/members">Back to members</Link>}
        />
      </Page>
    );
  }

  const record = member.data;
  const home = recordHome(record, roles);

  return (
    <Page
      title={record.name}
      tabTitle={`${record.name} · Member record`}
      actions={<Link to={home.to}>{home.label}</Link>}
    >
      <MemberHeader member={record} />
      <Tabs active={active} onSelect={handleSelectTab} />

      <TabPanel id="profile" active={active}>
        <MemberProfileTab member={record} key={`profile-${record.id}`} />
        {showsEmailPreferences(record) ? <MemberEmailPreferences member={record} /> : null}
      </TabPanel>
      <TabPanel id="memberships" active={active}>
        <MemberMembershipsTab member={record} />
      </TabPanel>
      <TabPanel id="payments" active={active}>
        <MemberPaymentsTab member={record} />
      </TabPanel>
      <TabPanel id="danger" active={active}>
        <MemberDangerZone member={record} />
      </TabPanel>
    </Page>
  );
}
