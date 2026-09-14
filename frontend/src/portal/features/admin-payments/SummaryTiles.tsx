/** The three headline figures above the payments dashboard. */
import { formatCents } from '../../components/Money';
import type { DashboardTotals } from './api';

export interface SummaryTilesProps {
  totals: DashboardTotals;
  isLoading?: boolean;
}

interface TileProps {
  label: string;
  cents: number;
  count: number;
}

function Tile({ label, cents, count }: TileProps) {
  return (
    <div className="stat-tile">
      <p className="eyebrow">{label}</p>
      <p className="stat-tile__value mono">{formatCents(cents)}</p>
      <p className="stat-tile__meta muted">
        {count} {count === 1 ? 'payment' : 'payments'}
      </p>
    </div>
  );
}

export function SummaryTiles({ totals, isLoading = false }: SummaryTilesProps) {
  if (isLoading) {
    return (
      <p className="muted" role="status">
        Loading totals…
      </p>
    );
  }

  return (
    <div className="stat-tiles">
      <Tile label="This month" cents={totals.thisMonth.cents} count={totals.thisMonth.count} />
      <Tile label="Year to date" cents={totals.yearToDate.cents} count={totals.yearToDate.count} />
      <Tile
        label="Last 12 months"
        cents={totals.lastTwelveMonths.cents}
        count={totals.lastTwelveMonths.count}
      />
    </div>
  );
}
