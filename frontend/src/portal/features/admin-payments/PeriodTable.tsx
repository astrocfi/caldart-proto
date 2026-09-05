/**
 * Money per month or per year, with one column per provider (PLAN §6.8).
 *
 * Newest first: an administrator looking at this page almost always wants the
 * period they are in.
 */
import type { PaymentPeriodSummary } from '../../api/types';
import { EmptyState } from '../../components/EmptyState';
import { formatCents } from '../../components/Money';
import { PROVIDER_LABELS } from './labels';
import { providersIn } from './api';
import type { SummaryGroup } from './api';

export interface PeriodTableProps {
  rows: PaymentPeriodSummary[];
  group: SummaryGroup;
  onGroupChange: (group: SummaryGroup) => void;
  isLoading?: boolean;
}

/** `2026-03` -> `March 2026`; `2026` is already readable. */
export function periodLabel(period: string, group: SummaryGroup): string {
  if (group === 'year') return period;
  const [year, month] = period.split('-');
  if (!year || !month) return period;
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

export function PeriodTable({ rows, group, onGroupChange, isLoading = false }: PeriodTableProps) {
  const providers = providersIn(rows);
  const newestFirst = [...rows].reverse();

  return (
    <section className="stack period-table" aria-labelledby="payments-by-period">
      <div className="period-table__bar">
        <h2 className="period-table__title" id="payments-by-period">
          Payments by period
        </h2>
        <div className="segmented" role="group" aria-label="Group payments by">
          {(['month', 'year'] as SummaryGroup[]).map((option) => (
            <button
              key={option}
              type="button"
              className="segmented__option"
              aria-pressed={group === option}
              onClick={() => onGroupChange(option)}
            >
              {option === 'month' ? 'Month' : 'Year'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="muted" role="status">
          Loading summary…
        </p>
      ) : newestFirst.length === 0 ? (
        <EmptyState
          title="No payments in this range"
          description="Widen the date filter, or clear it to see everything."
        />
      ) : (
        <div className="table-wrap">
          <table>
            <caption className="visually-hidden">
              Payment totals by {group}, with a column for each provider
            </caption>
            <thead>
              <tr>
                <th scope="col">{group === 'month' ? 'Month' : 'Year'}</th>
                <th scope="col" className="numeric">
                  Payments
                </th>
                <th scope="col" className="numeric">
                  Dues
                </th>
                <th scope="col" className="numeric">
                  Contributions
                </th>
                {providers.map((provider) => (
                  <th key={provider} scope="col" className="numeric">
                    {PROVIDER_LABELS[provider]}
                  </th>
                ))}
                <th scope="col" className="numeric">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {newestFirst.map((row) => (
                <tr key={row.period}>
                  <th scope="row">{periodLabel(row.period, group)}</th>
                  <td className="numeric">{row.count}</td>
                  <td className="numeric">{formatCents(row.plan_cents)}</td>
                  <td className="numeric">{formatCents(row.contribution_cents)}</td>
                  {providers.map((provider) => (
                    <td key={provider} className="numeric">
                      {row.by_provider[provider] ? formatCents(row.by_provider[provider]) : '—'}
                    </td>
                  ))}
                  <td className="numeric period-table__total">{formatCents(row.total_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
