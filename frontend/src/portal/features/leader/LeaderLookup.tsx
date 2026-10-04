/**
 * The shape both DART leader checks share: one search box that queries as the
 * leader types, a list of one-line results with the verdict at the far end, and
 * the chosen record's card in place of the search.
 *
 * The chosen record lives in the query string, so a leader can send a link, use
 * the back button, and reload without losing the card.  Picking a result moves the
 * focus to its card, and **Back to search** moves it back to the search box.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, Key, ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import type { LeaderGoNoGo } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useDebounced } from '@/portal/components/useDebounced';
import './leader.css';

/** The part of a query result the lookup reads: a `useQuery` result satisfies it. */
export interface LookupResults<T> {
  data: T[] | undefined;
  isFetching: boolean;
  isSuccess: boolean;
}

export interface LeaderLookupProps<T> {
  /** The page heading. */
  title: string;
  /** The line under the heading while the search is showing. */
  lede: string;
  /** Shown above the search box while no record is open, such as a report's downloads. */
  aboveSearch?: ReactNode;
  /** The query-string key that holds the chosen record. */
  param: string;
  /** The chosen record from the raw query-string value, or `null` when it names none. */
  parse: (raw: string) => string | null;
  /** The search box's label. */
  label: string;
  /** The search box's hint. */
  hint: string;
  placeholder: string;
  /** An extra class for the search box, such as `num` for registrations. */
  inputClassName?: string;
  /** What the results are, in the plural, for the screen-reader count. */
  noun: string;
  /** The query hook behind the results; it must stay idle for a blank term. */
  useResults: (term: string) => LookupResults<T>;
  rowKey: (row: T) => Key;
  /** The query-string value that picking `row` writes. */
  rowValue: (row: T) => string;
  /** The inside of a result row: what the record is, then a `GoMark`. */
  renderRow: (row: T) => ReactNode;
  /** What to say when a search finds nothing. */
  renderEmpty: (term: string) => ReactNode;
  /** The chosen record's card; **Back to search** above it returns to the search. */
  renderSelected: (value: string) => ReactNode;
}

/** A search that queries as the leader types, and the card of the result they pick. */
export function LeaderLookup<T>({
  title,
  lede,
  aboveSearch,
  param,
  parse,
  label,
  hint,
  placeholder,
  inputClassName,
  noun,
  useResults,
  rowKey,
  rowValue,
  renderRow,
  renderEmpty,
  renderSelected,
}: LeaderLookupProps<T>): JSX.Element {
  const [params, setParams] = useSearchParams();
  const selected = parse(params.get(param) ?? '');

  const [term, setTerm] = useState('');
  const debounced = useDebounced(term.trim());
  const search = useResults(selected === null ? debounced : '');

  // The focus follows the leader between the search and a card, once they have moved
  // between them; a page opened on a card or a search leaves it where the page puts it.
  const searchRef = useRef<HTMLInputElement>(null);
  const selectedRef = useRef<HTMLDivElement>(null);
  const shownRef = useRef(selected);
  useEffect(() => {
    if (shownRef.current === selected) return;
    shownRef.current = selected;
    (selected === null ? searchRef : selectedRef).current?.focus();
  }, [selected]);

  if (selected !== null) {
    return (
      <Page title={title}>
        <div className="leader-back">
          <Link to={{ search: '' }}>Back to search</Link>
        </div>
        <div ref={selectedRef} tabIndex={-1} className="stack leader-selected">
          {renderSelected(selected)}
        </div>
      </Page>
    );
  }

  const results = search.data ?? [];
  const searched = debounced.length > 0 && search.isSuccess;

  return (
    <Page title={title} lede={lede}>
      {aboveSearch}
      <Card>
        <Field label={label} hint={hint}>
          {(field) => (
            <input
              {...field}
              ref={searchRef}
              type="search"
              autoComplete="off"
              spellCheck={false}
              className={inputClassName}
              value={term}
              placeholder={placeholder}
              onChange={(event) => setTerm(event.target.value)}
            />
          )}
        </Field>

        <p className="visually-hidden" role="status">
          {search.isFetching ? 'Searching' : searched ? `${results.length} ${noun} found` : ''}
        </p>

        {search.isFetching && search.data === undefined ? (
          <p className="muted">Searching…</p>
        ) : null}

        {results.length > 0 ? (
          <ul className="leader-search__results">
            {results.map((row) => (
              <li key={rowKey(row)} className="leader-search__result">
                <button
                  type="button"
                  className="leader-search__button"
                  onClick={() => setParams({ [param]: rowValue(row) })}
                >
                  {renderRow(row)}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {searched && results.length === 0 ? renderEmpty(debounced) : null}
      </Card>
    </Page>
  );
}

/**
 * Whether a person is a go: all three verdicts the server reports have to be true.
 *
 * The same three booleans drive the verdict band on the status card, so the list
 * and the card can never disagree about who may fly.
 */
export function isReady(goNoGo: LeaderGoNoGo): boolean {
  return goNoGo.membership && goNoGo.medical && goNoGo.verified;
}

export interface GoMarkProps {
  go: boolean;
  /** What the dot says to a screen reader, such as `Cleared to fly`. */
  label: string;
}

/**
 * GO or NO-GO at the far end of a result row, so a leader scanning the list
 * reads one column of verdicts before opening any card.
 */
export function GoMark({ go, label }: GoMarkProps): JSX.Element {
  return (
    <span className="leader-search__readiness">
      <StatusDot tone={go ? 'current' : 'expired'} label={label} hideWord />
      <span
        className={`leader-search__verdict ${
          go ? 'leader-search__verdict--go' : 'leader-search__verdict--nogo'
        }`}
      >
        {go ? 'GO' : 'NO-GO'}
      </span>
    </span>
  );
}
