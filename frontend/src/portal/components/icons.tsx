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
import type { JSX, ReactNode } from 'react';

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

/**
 * The square, stroked frame every rich text toolbar icon is drawn in, so each
 * icon below is only its own lines.
 */
function OutlineIcon({ size, children }: IconProps & { children: ReactNode }): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width={size ?? DEFAULT_SIZE}
      height={size ?? DEFAULT_SIZE}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

/** A heavy B: make the selected words bold. */
export function BoldIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <path d="M7 5h6a3.5 3.5 0 0 1 0 7H7z" strokeWidth="2.5" />
      <path d="M7 12h7a3.5 3.5 0 0 1 0 7H7z" strokeWidth="2.5" />
    </OutlineIcon>
  );
}

/** A slanted I: make the selected words italic. */
export function ItalicIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <path d="M10 5h8" />
      <path d="M6 19h8" />
      <path d="M14 5l-4 14" />
    </OutlineIcon>
  );
}

/** An H: make the line a heading. */
export function HeadingIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <path d="M6 5v14" />
      <path d="M18 5v14" />
      <path d="M6 12h12" />
    </OutlineIcon>
  );
}

/** Three dotted lines: a bulleted list. */
export function BulletListIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <path d="M9 6h11" />
      <path d="M9 12h11" />
      <path d="M9 18h11" />
      <path d="M4.5 6h.01" strokeWidth="3" />
      <path d="M4.5 12h.01" strokeWidth="3" />
      <path d="M4.5 18h.01" strokeWidth="3" />
    </OutlineIcon>
  );
}

/** Three numbered lines: a numbered list. */
export function NumberedListIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <path d="M10 6h10" />
      <path d="M10 12h10" />
      <path d="M10 18h10" />
      <path d="M4 5l1.5-1v5" />
      <path d="M3.5 14.5a1.5 1.5 0 0 1 3 .5L3.5 19h3" />
    </OutlineIcon>
  );
}

/** Two chain links: link the selected words to an address. */
export function LinkIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <path d="M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1" />
      <path d="M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1" />
    </OutlineIcon>
  );
}

/** A framed landscape: put a picture in. */
export function ImageIcon({ size }: IconProps): JSX.Element {
  return (
    <OutlineIcon size={size}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 16l5-5 4 4 3-3 6 6" />
      <path d="M15.5 9h.01" strokeWidth="3" />
    </OutlineIcon>
  );
}
