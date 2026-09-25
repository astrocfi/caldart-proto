/**
 * A bare icon control: one icon, no border, no background, and no words.
 *
 * Where a row already says what it is about -- an attached aircraft, a person on
 * a DART -- a control with a border and a label repeats the row.  `IconButton`
 * draws the icon alone in the muted text color and comes forward on hover and on
 * keyboard focus, so a list of rows reads as a list rather than as a wall of
 * buttons.  It is never a `Button`: the two look nothing alike on purpose.
 */
import type { ButtonHTMLAttributes, JSX } from 'react';

import { ArrowDownIcon, ArrowUpIcon, TrashcanIcon } from './icons';

/** The icons a bare icon button can show. */
export type IconName = 'trashcan' | 'arrow-up' | 'arrow-down';

const ICONS: Record<IconName, () => JSX.Element> = {
  trashcan: TrashcanIcon,
  'arrow-up': ArrowUpIcon,
  'arrow-down': ArrowDownIcon,
};

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Which icon to draw. */
  icon: IconName;
  /** The accessible name, e.g. "Remove N12345" or "Move person 2 up". */
  label: string;
}

/**
 * A button that shows one icon and nothing else.
 *
 * `label` is the whole of the accessible name, and it is the tooltip too unless
 * the caller passes its own `title` -- the reason the button is disabled, say --
 * which wins.  Every other `<button>` attribute is passed straight through, and
 * the type defaults to `button` so the control never submits the form it sits
 * in.  A caller's `className` joins `icon-button` rather than replacing it.
 */
export function IconButton({
  icon,
  label,
  className,
  title,
  type = 'button',
  ...rest
}: IconButtonProps): JSX.Element {
  const Icon = ICONS[icon];
  return (
    <button
      type={type}
      className={['icon-button', className ?? ''].filter(Boolean).join(' ')}
      aria-label={label}
      title={title ?? label}
      {...rest}
    >
      <Icon />
    </button>
  );
}
