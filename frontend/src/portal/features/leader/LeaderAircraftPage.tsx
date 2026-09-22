/**
 * `/leader/aircraft` — check one tail number's insurance.
 *
 * The registration lives in the query string so the card survives a reload
 * and can be sent to another leader.
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
import { normalizeNNumber } from '@/portal/features/aircraft/insurance';
import { AircraftStatusCard } from './AircraftStatusCard';
import { useLeaderAircraft } from './api';
import './leader.css';

/** Looks up one tail number and renders its insurance status card. */
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

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const next = normalizeNNumber(term);
    setParams(next ? { n_number: next } : {});
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
          <Field label="N-number" hint="12345, n12345 and N-12345 all find the same aircraft.">
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
