/**
 * `/admin/members/:id` — one member record, in four tabs.
 *
 * The tab is held in the query string so a colleague can be sent straight to
 * the memberships table, and the tab strip follows the WAI-ARIA tabs pattern:
 * arrow keys move between tabs, Home and End jump to the ends.
 */
import { useRef } from 'react';
import type { JSX } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import type { MemberDetail } from '@/portal/api/types';
import { ACCOUNT_KIND_LABELS, roleLabel } from '@/portal/choices';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { MembershipChip } from '@/portal/components/StatusChip';
import { MemberDangerZone } from './MemberDangerZone';
import { MemberMembershipsTab } from './MemberMembershipsTab';
import { MemberPaymentsTab } from './MemberPaymentsTab';
import { MemberProfileTab } from './MemberProfileTab';
import { useMember } from './api';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'memberships', label: 'Memberships' },
  { id: 'payments', label: 'Payments' },
  { id: 'danger', label: 'Danger zone' },
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
    <div className="cluster" role="tablist" aria-label="Member record sections">
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
          className={`button button--small ${active === tab.id ? 'button--secondary' : 'button--quiet'}`}
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

function MemberHeader({ member }: { member: MemberDetail }) {
  return (
    <Card>
      <div className="cluster">
        <MembershipChip membership={member.membership} />
        {member.membership.plan ? <span className="muted">{member.membership.plan}</span> : null}
        {member.membership.is_lifetime ? null : (
          <span className="muted">
            expires <DateText value={member.membership.expires_on} />
          </span>
        )}
        <span className="muted">
          joined <DateText value={member.joined_on} />
        </span>
        <span className="muted">
          {member.profile_updated_at === null ? (
            'never edited'
          ) : (
            <>
              updated <DateText value={member.profile_updated_at} />
            </>
          )}
        </span>
        {member.kind === 'donor' ? (
          <span className="chip chip--neutral">{ACCOUNT_KIND_LABELS.donor}</span>
        ) : null}
        {member.is_active ? null : <span className="chip chip--bad">Account deactivated</span>}
      </div>
      <p className="muted">
        <a href={`mailto:${member.email}`}>{member.email}</a> ·{' '}
        {member.roles.map(roleLabel).join(', ')}
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

  const handleSelectTab = (tab: TabId) => {
    const next = new URLSearchParams(params);
    if (tab === 'profile') next.delete('tab');
    else next.set('tab', tab);
    setParams(next, { replace: true });
  };

  if (member.isPending) {
    return (
      <Page title="Member" eyebrow="Administration">
        <p role="status">Loading…</p>
      </Page>
    );
  }

  if (member.isError || !member.data) {
    return (
      <Page title="Member" eyebrow="Administration">
        <EmptyState
          title="That member could not be loaded"
          description="They may have been deleted."
          action={<ButtonLink to="/admin/members">Back to members</ButtonLink>}
        />
      </Page>
    );
  }

  const record = member.data;

  return (
    <Page
      title={record.name}
      eyebrow="Member record"
      actions={
        <ButtonLink to="/admin/members" variant="quiet">
          Back to members
        </ButtonLink>
      }
    >
      <MemberHeader member={record} />
      <Tabs active={active} onSelect={handleSelectTab} />

      <TabPanel id="profile" active={active}>
        <MemberProfileTab member={record} key={`profile-${record.id}`} />
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
