/**
 * `/leader` — one search box, then the status card.
 *
 * The chosen member lives in the query string, so a leader can send a link,
 * use the back button, and reload without losing the card.
 */
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Field } from '../../components/Field';
import { Page } from '../../components/Page';
import { StatusChip } from '../../components/StatusChip';
import { looksLikeRegistration, normalizeNNumber } from '../aircraft/insurance';
import { useDebounced } from '../aircraft/useDebounced';
import { MemberStatusCard } from './MemberStatusCard';
import { useLeaderSearch, useMemberStatus } from './api';
import './leader.css';

export function LeaderSearchPage() {
  const [params, setParams] = useSearchParams();
  // `?member=` comes from a link or a hand-edited URL: only a real record id
  // opens the card, so a stray value cannot become a request for member NaN.
  const selected = Number(params.get('member'));
  const memberId = Number.isInteger(selected) && selected > 0 ? selected : null;

  const [term, setTerm] = useState('');
  const debounced = useDebounced(term.trim());
  const search = useLeaderSearch(memberId === null ? debounced : '');
  const status = useMemberStatus(memberId);

  const choose = (userId: number): void => {
    setParams({ member: String(userId) });
  };

  const back = (): void => {
    setParams({});
  };

  if (memberId !== null) {
    return (
      <Page title="Member check" eyebrow="DART leader">
        <div className="leader-back">
          <Button variant="quiet" small onClick={back}>
            ← Back to search
          </Button>
        </div>
        {status.isPending ? <p className="muted">Loading the status card…</p> : null}
        {status.isError ? (
          <EmptyState
            title="That member could not be loaded"
            description={
              status.error instanceof ApiError && status.error.status === 404
                ? 'No member with that id. They may have been removed.'
                : (status.error as Error).message
            }
            action={
              <Button variant="secondary" onClick={back}>
                Search again
              </Button>
            }
          />
        ) : null}
        {status.data ? <MemberStatusCard status={status.data} /> : null}
      </Page>
    );
  }

  const results = search.data ?? [];
  const searched = debounced.length > 0 && search.isSuccess;

  return (
    <Page
      title="Member check"
      eyebrow="DART leader"
      lede="Look someone up before a flight: membership, medical, certificate and the insurance on the planes they fly."
    >
      <Card>
        <Field label="Name, email or N-number" hint="Try “Reyes”, “marta@example.org” or “N172SP”.">
          {(field) => (
            <input
              {...field}
              type="search"
              autoComplete="off"
              spellCheck={false}
              value={term}
              placeholder="Search members"
              onChange={(event) => setTerm(event.target.value)}
            />
          )}
        </Field>

        <p className="visually-hidden" role="status">
          {search.isFetching ? 'Searching' : searched ? `${results.length} members found` : ''}
        </p>

        {search.isFetching && !search.data ? <p className="muted">Searching…</p> : null}

        {results.length > 0 ? (
          <ul className="leader-search__results">
            {results.map((result) => (
              <li key={result.user_id} className="leader-search__result">
                <button
                  type="button"
                  className="leader-search__button"
                  onClick={() => choose(result.user_id)}
                >
                  <span className="leader-search__name">{result.name}</span>
                  <span className="leader-search__meta">
                    {result.email}
                    {result.dart ? ` · ${result.dart}` : ''}
                  </span>
                  <StatusChip
                    tone={
                      result.membership_status === 'current'
                        ? 'current'
                        : result.membership_status === 'expired'
                          ? 'expired'
                          : 'none'
                    }
                    label={
                      result.membership_status === 'current'
                        ? 'Member current'
                        : result.membership_status === 'expired'
                          ? 'Member expired'
                          : 'Never joined'
                    }
                  />
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {searched && results.length === 0 ? (
          <EmptyState
            title="Nobody matches that"
            description={
              looksLikeRegistration(debounced)
                ? 'No member lists that aircraft. You can still check the aircraft itself.'
                : 'Try a surname, part of an email address, or the N-number of the aircraft.'
            }
            action={
              looksLikeRegistration(debounced) ? (
                <Link
                  className="button button--secondary button--small"
                  to={`/leader/aircraft?n_number=${encodeURIComponent(normalizeNNumber(debounced))}`}
                >
                  Check {normalizeNNumber(debounced)}
                </Link>
              ) : null
            }
          />
        ) : null}
      </Card>
    </Page>
  );
}
