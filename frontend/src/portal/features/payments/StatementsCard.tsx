/**
 * One download button per calendar year the member contributed in.
 *
 * A year in which only dues were paid has no statement: dues are not a gift,
 * so there is nothing for the 501(c)(3) wording to cover.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { statementUrl, useStatementYears } from './api';

/** The contribution statements card on the member's Payments screen. */
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
          title="Your statements could not be loaded"
          description="Please reload the page, or contact CalDART if it keeps happening."
        />
      ) : years.length === 0 ? (
        <EmptyState
          title="No statements yet"
          description="A statement covers a calendar year you contributed in. Dues on their own are not a contribution, so a year of dues alone has none."
        />
      ) : (
        <>
          <p>
            Each statement lists every contribution that settled in the year, less anything
            refunded, with the year&rsquo;s total and the 501(c)(3) wording.
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
