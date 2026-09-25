/**
 * `/leader` — the member check: one search box, then the status card.
 *
 * The chosen member is kept in the query string as `?member=<id>`.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { LeaderGoNoGo, LeaderSearchResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { EmptyState } from '@/portal/components/EmptyState';
import { looksLikeRegistration, normalizeNNumber } from '@/portal/features/aircraft/insurance';
import { GoMark, LeaderLookup } from './LeaderLookup';
import { MemberStatusCard } from './MemberStatusCard';
import { useLeaderSearch, useMemberStatus } from './api';
import './leader.css';

/**
 * Whether a search row is a go: both counts the server reports have to be true.
 *
 * The same two booleans drive the verdict band on the status card, so the list
 * and the card can never disagree about who may fly.
 */
function isReady(goNoGo: LeaderGoNoGo): boolean {
  return goNoGo.membership && goNoGo.medical;
}

/**
 * `?member=` comes from a link or a hand-edited URL: only a real record id
 * opens the card, so a stray value cannot become a request for member NaN.
 */
function parseMemberId(raw: string): string | null {
  const id = Number(raw);
  return Number.isInteger(id) && id > 0 ? String(id) : null;
}

/** Searches members and renders the chosen one's pre-flight status card. */
export function LeaderSearchPage(): JSX.Element {
  return (
    <LeaderLookup<LeaderSearchResult>
      title="Member check"
      lede="Look someone up before a flight: membership, medical, certificate, and the insurance on the planes they fly."
      param="member"
      parse={parseMemberId}
      label="Name, email, phone, or N-number"
      hint="Try “Reyes”, “marta@example.org”, “415-555-0100”, or “N172SP”."
      placeholder="Search members"
      noun="members"
      useResults={useLeaderSearch}
      rowKey={(result) => result.user_id}
      rowValue={(result) => String(result.user_id)}
      renderRow={(result) => {
        const ready = isReady(result.go_no_go);
        return (
          <>
            <span className="leader-search__name">{result.name}</span>
            <GoMark go={ready} label={ready ? 'Cleared to fly' : 'Not cleared to fly'} />
          </>
        );
      }}
      renderEmpty={(term) => <NoMemberFound term={term} />}
      renderSelected={(id, handleBack) => <MemberCheck userId={Number(id)} onBack={handleBack} />}
    />
  );
}

interface NoMemberFoundProps {
  term: string;
}

/** Nobody matched: an N-number is offered to the aircraft check instead. */
function NoMemberFound({ term }: NoMemberFoundProps): JSX.Element {
  const registration = looksLikeRegistration(term) ? normalizeNNumber(term) : null;
  return (
    <EmptyState
      title="Nobody matches that"
      description={
        registration !== null
          ? 'No member lists that aircraft. You can still check the aircraft itself.'
          : 'Try a surname, part of an email address, a phone number, or an N-number.'
      }
      action={
        registration !== null ? (
          <Link
            className="button button--secondary button--small"
            to={`/leader/aircraft?aircraft=${encodeURIComponent(registration)}`}
          >
            Check {registration}
          </Link>
        ) : null
      }
    />
  );
}

interface MemberCheckProps {
  userId: number;
  onBack: () => void;
}

/** The chosen member's status card, or why it could not be loaded. */
function MemberCheck({ userId, onBack: handleBack }: MemberCheckProps): JSX.Element {
  const status = useMemberStatus(userId);
  return (
    <>
      {status.isPending ? <p className="muted">Loading the status card…</p> : null}
      {status.isError ? (
        <EmptyState
          title="That member could not be loaded"
          description={
            status.error instanceof ApiError && status.error.status === 404
              ? 'No member with that id. They may have been removed.'
              : status.error.message
          }
          action={
            <Button variant="secondary" onClick={handleBack}>
              Search again
            </Button>
          }
        />
      ) : null}
      {status.data ? <MemberStatusCard status={status.data} /> : null}
    </>
  );
}
