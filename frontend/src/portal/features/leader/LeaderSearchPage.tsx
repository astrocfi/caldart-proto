/**
 * `/leader` — the member check: one search box, then the status card.
 *
 * The chosen member is kept in the query string as `?member=<id>`.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { LeaderSearchResult } from '@/portal/api/types';
import { EmptyState } from '@/portal/components/EmptyState';
import { looksLikeRegistration, normalizeNNumber } from '@/portal/features/aircraft/insurance';
import { reportExportUrl } from '@/portal/reports/api';
import { GoMark, LeaderLookup, isReady } from './LeaderLookup';
import { MemberStatusCard } from './MemberStatusCard';
import { useLeaderSearch, useMemberStatus } from './api';
import './leader.css';

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
      lede="Look someone up before a flight: membership, medical, certificate, photo ID, and the insurance on the planes they fly."
      aboveSearch={<VerificationReportLinks />}
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
            <span className="leader-search__who">
              <span className="leader-search__name">{result.name}</span>
              <span className="leader-search__meta">{resultMeta(result)}</span>
            </span>
            <GoMark go={ready} label={ready ? 'Cleared to fly' : 'Not cleared to fly'} />
          </>
        );
      }}
      renderEmpty={(term) => <NoMemberFound term={term} />}
      renderSelected={(id) => <MemberCheck userId={Number(id)} />}
    />
  );
}

/**
 * What tells two people of one name apart in the results: their DART, named as one,
 * and their email address, such as *Monterey DART · marta@example.org*.
 */
function resultMeta(result: LeaderSearchResult): string {
  const dart = result.dart === null ? 'No DART' : `${result.dart} DART`;
  return `${dart} · ${result.email}`;
}

/** The caption of the verification report's downloads, which names the group. */
const REPORT_CAPTION = 'Everything nobody has checked yet:';

/**
 * The verification report, downloaded with its default filter: every item nobody has
 * verified yet.
 */
function VerificationReportLinks(): JSX.Element {
  return (
    <div className="cluster leader-report" role="group" aria-labelledby="leader-report-caption">
      <span id="leader-report-caption">{REPORT_CAPTION}</span>
      <a
        className="button button--quiet button--small"
        href={reportExportUrl('verification', 'csv', {})}
      >
        Export CSV
      </a>
      <a
        className="button button--quiet button--small"
        href={reportExportUrl('verification', 'pdf', {})}
      >
        Export PDF
      </a>
    </div>
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
}

/**
 * The chosen member's status card, or why it could not be loaded.  **Back to search**
 * above the card is the way back, so the card offers no second one.
 */
function MemberCheck({ userId }: MemberCheckProps): JSX.Element {
  const status = useMemberStatus(userId);
  return (
    <>
      {status.isPending ? <p className="muted">Loading the status card…</p> : null}
      {status.isError ? (
        status.error instanceof ApiError && status.error.status === 404 ? (
          <EmptyState
            title="We could not find that person"
            description="Their account may have been deleted."
          />
        ) : (
          <EmptyState
            title="That person's check didn't load"
            description="Try again in a moment."
          />
        )
      ) : null}
      {status.data ? <MemberStatusCard userId={userId} status={status.data} /> : null}
    </>
  );
}
