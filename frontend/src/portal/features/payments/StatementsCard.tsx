/**
 * One download button per calendar year the member paid dues or contributed in.
 *
 * Dues and contributions are both tax deductible, so both are on the statement.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { statementUrl, useStatementYears } from './api';

/** The contribution statements card on the member's My payments screen. */
export function StatementsCard(): JSX.Element {
  const statements = useStatementYears();
  const years = statements.data?.years ?? [];

  return (
    <Card eyebrow="For your tax return" title="Contribution statements">
      {statements.isPending ? (
        <p className="muted" role="status">
          Loading…
        </p>
      ) : statements.error ? (
        // A year missing from a failed read is not a year without a statement.
        <EmptyState
          title="Your statements didn't load"
          description="Reload the page, or contact CalDART if it keeps happening."
        />
      ) : years.length === 0 ? (
        <EmptyState
          title="No statements yet"
          description="A statement covers a calendar year you paid dues or gave a contribution in."
        />
      ) : (
        <>
          <p>
            Each statement lists your dues and contributions that settled in the year, less anything
            refunded, with the year&rsquo;s total and the wording your tax preparer needs.
          </p>
          <ul className="payments__statements" role="list">
            {years.map((year) => (
              <li key={year}>
                <a className="button button--secondary" href={statementUrl(year)} download>
                  {year} statement
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
