/** The three headline periods above the finance overview. */
import type { JSX } from 'react';

import { formatCents } from '@/portal/components/Money';
import type { DashboardTotals, Totals } from './api';

export interface SummaryTilesProps {
  totals: DashboardTotals;
  isLoading?: boolean;
}

interface TileProps {
  label: string;
  totals: Totals;
}

function Tile({ label, totals }: TileProps) {
  return (
    <div className="stat-tile">
      <p className="eyebrow">{label}</p>
      <p className="stat-tile__value mono">{formatCents(totals.grossCents)}</p>
      <p className="stat-tile__meta muted">
        {totals.count} {totals.count === 1 ? 'payment' : 'payments'}
      </p>
      <dl className="stat-tile__breakdown">
        <div>
          <dt>Fees</dt>
          <dd className="mono">{formatCents(totals.feeCents)}</dd>
        </div>
        <div>
          <dt>Net</dt>
          <dd className="mono">{formatCents(totals.netCents)}</dd>
        </div>
        <div>
          <dt>Refunded</dt>
          <dd className="mono">{formatCents(totals.refundedCents)}</dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * Gross, fees, net and refunds for this month, the year to date and the last
 * twelve months.
 */
export function SummaryTiles({ totals, isLoading = false }: SummaryTilesProps): JSX.Element {
  if (isLoading) {
    return (
      <p className="muted" role="status">
        Loading totals…
      </p>
    );
  }

  return (
    <div className="stat-tiles">
      <Tile label="This month" totals={totals.thisMonth} />
      <Tile label="Year to date" totals={totals.yearToDate} />
      <Tile label="Last 12 months" totals={totals.lastTwelveMonths} />
    </div>
  );
}
