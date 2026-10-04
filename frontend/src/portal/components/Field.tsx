import { useId } from 'react';
import type { JSX, ReactElement, ReactNode } from 'react';

export interface FieldProps {
  label: string;
  /**
   * Words a screen reader hears after the label, where several boxes share one label,
   * such as ` of person 2` on each row of a list of people.
   */
  labelSuffix?: string;
  /** Rendered with the field's `id`, `aria-describedby`, and `aria-invalid`. */
  children: (props: {
    id: string;
    'aria-describedby': string | undefined;
    'aria-invalid': boolean | undefined;
  }) => ReactElement;
  hint?: ReactNode;
  /**
   * A standing fact about the value, such as its verification mark: drawn under the box
   * and kept while an error shows, where a hint gives way to the error.
   */
  status?: ReactNode;
  error?: string | null;
  required?: boolean;
}

/**
 * Label, hint, control, and error, wired up for screen readers.
 *
 * The hint sits under the label, where it is read before the box is filled in, and the
 * error under the box it is about. While an error shows, the hint is hidden and the
 * error describes the box, so the two never disagree on screen. In one column the hidden
 * hint gives its line up to the error (`field__hint--hidden` takes it out of the flow), so
 * no blank band opens between the label and the box; in a two-column form grid it keeps
 * its space, so the boxes of one row stay level as the error comes and goes. A field with
 * no hint still draws an empty hint slot, which a two-column form grid gives one line, so
 * the boxes in one row line up whether or not each has a hint. A status sits under the
 * box, above any error, and describes the box whether or not an error shows.
 */
export function Field({
  label,
  labelSuffix,
  children,
  hint,
  status,
  error,
  required,
}: FieldProps): JSX.Element {
  const id = useId();
  const hasError = error !== undefined && error !== null && error !== '';
  const hasHint = hint !== undefined && hint !== null && hint !== '';
  const showHint = hasHint && !hasError;
  const hintId = showHint ? `${id}-hint` : undefined;
  const errorId = hasError ? `${id}-error` : undefined;
  const hasStatus = status !== undefined && status !== null && status !== '';
  const statusId = hasStatus ? `${id}-status` : undefined;
  const describedBy = [errorId ?? hintId, statusId].filter(Boolean).join(' ') || undefined;

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
        {labelSuffix === undefined ? null : <span className="visually-hidden">{labelSuffix}</span>}
        {required ? (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {hasHint ? (
        // Hidden rather than removed under an error, so a two-column grid keeps its row.
        <span
          className={showHint ? 'field__hint' : 'field__hint field__hint--hidden'}
          id={hintId}
          aria-hidden={showHint ? undefined : true}
          style={showHint ? undefined : { visibility: 'hidden' }}
        >
          {hint}
        </span>
      ) : (
        <span className="field__hint-slot" aria-hidden="true" />
      )}
      {children({
        id,
        'aria-describedby': describedBy,
        'aria-invalid': hasError ? true : undefined,
      })}
      {hasStatus ? (
        <span className="field__status" id={statusId}>
          {status}
        </span>
      ) : null}
      {hasError ? (
        <span className="field__error" id={errorId} role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
