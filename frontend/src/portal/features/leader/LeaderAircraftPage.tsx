/**
 * `/leader/aircraft` — check one tail number's insurance.
 *
 * The box suggests aircraft as the leader types, the way the member check
 * does, so a half-remembered registration or a model name still finds the
 * airplane.  The chosen registration lives in the query string, so the card
 * survives a reload and can be sent to another leader.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { useDebounced } from '@/portal/components/useDebounced';
import { InsuranceChip, useAircraftSearch } from '@/portal/features/aircraft';
import { normalizeNNumber } from '@/portal/features/aircraft/insurance';
import { AircraftStatusCard } from './AircraftStatusCard';
import { useLeaderAircraft } from './api';
import './leader.css';

/** Suggests aircraft as the leader types, and renders the chosen one's status card. */
export function LeaderAircraftPage(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const asked = params.get('n_number') ?? '';
  const [term, setTerm] = useState(asked);

  // A link from the member search arrives with the registration already set.
  useEffect(() => {
    setTerm(asked);
  }, [asked]);

  const normalized = normalizeNNumber(asked);
  const query = useLeaderAircraft(normalized);

  const debounced = useDebounced(term.trim());
  // Once an aircraft is chosen the box holds its registration, and searching
  // for what is already on screen would only offer it back.
  const search = useAircraftSearch(debounced === normalized ? '' : debounced);
  const matches = search.data?.matches ?? [];
  const searched = debounced.length > 0 && search.isSuccess;

  const choose = (nNumber: string): void => {
    setParams(nNumber ? { n_number: nNumber } : {});
  };

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    choose(normalizeNNumber(term));
  };

  const notFound = query.error instanceof ApiError && query.error.status === 404;

  return (
    <Page
      title="Aircraft check"
      eyebrow="DART leader"
      lede="Type the tail number of the aircraft in front of you to see whether its insurance is current."
    >
      <Card>
        <form onSubmit={handleSubmit}>
          <Field
            label="N-number"
            hint="Suggestions appear as you type. Registration, make, model, or owner all match."
          >
            {(field) => (
              <input
                {...field}
                type="search"
                autoComplete="off"
                spellCheck={false}
                className="mono"
                value={term}
                placeholder="N12345"
                onChange={(event) => setTerm(event.target.value)}
              />
            )}
          </Field>

          <p className="visually-hidden" role="status">
            {search.isFetching ? 'Searching' : searched ? `${matches.length} aircraft found` : ''}
          </p>

          {matches.length > 0 ? (
            <ul className="leader-search__results">
              {matches.map((aircraft) => (
                <li key={aircraft.id} className="leader-search__result">
                  <button
                    type="button"
                    className="leader-search__button"
                    onClick={() => choose(aircraft.n_number)}
                  >
                    <span className="leader-search__name mono">{aircraft.n_number}</span>
                    <span className="leader-search__meta">
                      {[aircraft.make, aircraft.model].filter(Boolean).join(' ')}
                      {aircraft.owner_name ? ` · ${aircraft.owner_name}` : ''}
                    </span>
                    <InsuranceChip aircraft={aircraft} />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          <Button type="submit">Check aircraft</Button>
        </form>
      </Card>

      {query.isFetching ? (
        <p className="muted" role="status">
          Checking {normalized}…
        </p>
      ) : null}

      {notFound ? (
        <EmptyState
          title={`${normalized} is not in the register`}
          description="Nobody has added this aircraft yet. Ask the pilot to add it to their profile, or add it from the aircraft register."
        />
      ) : null}

      {query.isError && !notFound ? (
        <EmptyState title="That check could not be run" description={query.error.message} />
      ) : null}

      {query.data ? <AircraftStatusCard aircraft={query.data} /> : null}
    </Page>
  );
}
