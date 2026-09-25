/**
 * The portal's inline icons.
 *
 * Each icon is a small SVG drawn in `currentColor`, square, and `1.25em` on a
 * side unless the caller asks for another size, so it takes the color and the
 * scale of whatever encloses it.  Each is `aria-hidden`: the control around the
 * icon carries the accessible name, and an icon that announced itself as well
 * would say the same thing twice.  They are written out here rather than pulled
 * from an icon library so the portal ships no icon dependency.
 */
import type { JSX } from 'react';

const DEFAULT_SIZE = '1.25em';

export interface IconProps {
  /** The edge of the square, as any CSS length; `1.25em` unless given. */
  size?: string;
}

/** A trashcan: remove or delete the thing the control names. */
export function TrashcanIcon({ size = DEFAULT_SIZE }: IconProps): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 7h16" />
      <path d="M10 4h4a1 1 0 0 1 1 1v2H9V5a1 1 0 0 1 1-1z" />
      <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </svg>
  );
}

/** An upward arrow: move the thing the control names one place earlier. */
export function ArrowUpIcon({ size = DEFAULT_SIZE }: IconProps): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 19V5" />
      <path d="M6 11l6-6 6 6" />
    </svg>
  );
}

/** A downward arrow: move the thing the control names one place later. */
export function ArrowDownIcon({ size = DEFAULT_SIZE }: IconProps): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5v14" />
      <path d="M6 13l6 6 6-6" />
    </svg>
  );
}
