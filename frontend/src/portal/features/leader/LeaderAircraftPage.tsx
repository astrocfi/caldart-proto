/**
 * `/leader/aircraft` — the aircraft check: one search box, then the insurance card.
 *
 * The search runs over the register as the leader types, so a half-remembered
 * registration, a model name, or an owner still finds the airplane.  The chosen
 * one is kept in the query string as `?aircraft=<n_number>`.
 */
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { Aircraft } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { EmptyState } from '@/portal/components/EmptyState';
import { useAircraftSearch } from '@/portal/features/aircraft';
import { normalizeNNumber } from '@/portal/features/aircraft/insurance';
import { AircraftStatusCard, isInsured } from './AircraftStatusCard';
import { GoMark, LeaderLookup } from './LeaderLookup';
import type { LookupResults } from './LeaderLookup';
import { useLeaderAircraft } from './api';
import './leader.css';

/** The register's matches for `term`, as the lookup's list of results. */
function useAircraftMatches(term: string): LookupResults<Aircraft> {
  const search = useAircraftSearch(term);
  return {
    data: search.data?.matches,
    isFetching: search.isFetching,
    isSuccess: search.isSuccess,
  };
}

/** `?aircraft=` in any spelling of the registration; a blank one names no aircraft. */
function parseRegistration(raw: string): string | null {
  const registration = normalizeNNumber(raw);
  return registration === '' ? null : registration;
}

/** Searches the aircraft register and renders the chosen aircraft's insurance card. */
export function LeaderAircraftPage(): JSX.Element {
  return (
    <LeaderLookup<Aircraft>
      title="Aircraft check"
      lede="Look up the aircraft in front of you to see whether its insurance is current."
      param="aircraft"
      parse={parseRegistration}
      label="Search by N-number"
      hint="Registration, make, model, or owner all match."
      placeholder="N12345"
      inputClassName="mono"
      noun="aircraft"
      useResults={useAircraftMatches}
      rowKey={(aircraft) => aircraft.id}
      rowValue={(aircraft) => aircraft.n_number}
      renderRow={(aircraft) => {
        const insured = isInsured(aircraft);
        return (
          <>
            <span className="leader-search__aircraft">
              <span className="leader-search__name mono">{aircraft.n_number}</span>
              <span className="leader-search__meta">
                {[aircraft.make, aircraft.model].filter(Boolean).join(' ')}
              </span>
            </span>
            <GoMark go={insured} label={insured ? 'Insured' : 'Not insured'} />
          </>
        );
      }}
      renderEmpty={() => (
        <EmptyState
          title="No aircraft matches that"
          description="Try the registration, the make or model, or the owner's name."
        />
      )}
      renderSelected={(nNumber, handleBack) => (
        <AircraftCheck nNumber={nNumber} onBack={handleBack} />
      )}
    />
  );
}

interface AircraftCheckProps {
  nNumber: string;
  onBack: () => void;
}

/** The chosen aircraft's insurance card, or why there is none. */
function AircraftCheck({ nNumber, onBack: handleBack }: AircraftCheckProps): JSX.Element {
  const query = useLeaderAircraft(nNumber);
  const notFound = query.error instanceof ApiError && query.error.status === 404;
  const searchAgain = (
    <Button variant="secondary" onClick={handleBack}>
      Search again
    </Button>
  );

  return (
    <>
      {query.isFetching ? (
        <p className="muted" role="status">
          Checking {nNumber}…
        </p>
      ) : null}

      {notFound ? (
        <EmptyState
          title={`${nNumber} is not in the register`}
          description="Nobody has added this aircraft yet. Ask the pilot to add it to their profile, or add it from the aircraft register."
          action={searchAgain}
        />
      ) : null}

      {query.isError && !notFound ? (
        <EmptyState
          title="That check could not be run"
          description={query.error.message}
          action={searchAgain}
        />
      ) : null}

      {query.data ? <AircraftStatusCard aircraft={query.data} /> : null}
    </>
  );
}
