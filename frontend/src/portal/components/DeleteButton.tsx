/**
 * The portal's one Remove-or-Delete control: a trashcan, sometimes with words.
 *
 * Every screen that used to spell "Remove" or "Delete" on a button uses this
 * instead, so one icon means one thing wherever it appears.  Where the control
 * sits in a row or on a form line it is icon-only and square, and `label` is
 * the whole of its accessible name; where the action is destructive enough to
 * ask for confirmation it keeps its words and the icon leads them.
 *
 * The trashcan is drawn inline in `currentColor` at `1em`, so it takes the
 * variant's color and the surrounding font size without an icon library.
 */
import type { JSX, ReactNode } from 'react';

import { Button } from './Button';
import type { ButtonProps } from './Button';

export interface DeleteButtonProps extends Omit<ButtonProps, 'children'> {
  /** The accessible name, e.g. "Remove N12345" or "Delete this DART". */
  label: string;
  /** The words shown after the icon; without them the button is icon-only. */
  children?: ReactNode;
}

/** The trashcan itself: decorative, since the button is already named. */
function TrashcanIcon(): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
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

/**
 * A quiet, small trashcan button that removes or deletes something.
 *
 * `label` names the thing being removed.  On an icon-only button it is both the
 * accessible name and the tooltip, unless the caller passes its own `title` —
 * the reason the button is disabled, say — which wins.  With `children` the words
 * follow the icon and `label` is not repeated as an `aria-label`.  Every other
 * `Button` prop — `onClick`, `disabled`, `type`, `variant`, `small` — is passed
 * straight through, and the variant defaults to `quiet` and the size to small.
 */
export function DeleteButton({
  label,
  children,
  variant = 'quiet',
  small = true,
  className,
  title,
  ...rest
}: DeleteButtonProps): JSX.Element {
  const isIconOnly = children === undefined;
  return (
    <Button
      variant={variant}
      small={small}
      className={[isIconOnly ? 'button--icon' : '', className ?? ''].filter(Boolean).join(' ')}
      title={title ?? (isIconOnly ? label : undefined)}
      {...(isIconOnly ? { 'aria-label': label } : {})}
      {...rest}
    >
      <TrashcanIcon />
      {children}
    </Button>
  );
}
