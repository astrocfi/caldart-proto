import { useId } from 'react';
import type { JSX } from 'react';

export interface FixedValueProps {
  label: string;
  value: string;
}

/**
 * A labeled value a form shows but does not let anyone change, such as the
 * recipient of a subscription being edited.  It reads as a group named by its
 * label, laid out like a `Field`.
 */
export function FixedValue({ label, value }: FixedValueProps): JSX.Element {
  const id = useId();
  return (
    <div className="field" role="group" aria-labelledby={id}>
      <span className="field__label" id={id}>
        {label}
      </span>
      <span>{value}</span>
    </div>
  );
}
