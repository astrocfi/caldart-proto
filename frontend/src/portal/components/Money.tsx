const USD = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
});

const USD_WHOLE = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

/** Format integer cents as US dollars. */
export function formatCents(cents: number, { whole = false }: { whole?: boolean } = {}): string {
  const value = cents / 100;
  return whole && Number.isInteger(value) ? USD_WHOLE.format(value) : USD.format(value);
}

export interface MoneyProps {
  cents: number | null | undefined;
  /** Drop the cents when the amount is whole dollars. */
  whole?: boolean;
  /** Shown when `cents` is null/undefined. */
  placeholder?: string;
}

/** Money always renders in the mono face with tabular figures. */
export function Money({ cents, whole = false, placeholder = '—' }: MoneyProps) {
  if (cents === null || cents === undefined) {
    return <span className="mono muted">{placeholder}</span>;
  }
  return <span className="mono">{formatCents(cents, { whole })}</span>;
}
