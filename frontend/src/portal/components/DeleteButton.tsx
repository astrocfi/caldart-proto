/**
 * The portal's one Remove-or-Delete control: a trashcan, sometimes with words.
 *
 * Every screen that used to spell "Remove" or "Delete" on a button uses this
 * instead, so one icon means one thing wherever it appears.  Where the control
 * sits in a row or on a form line it is a bare trashcan and `label` is the whole
 * of its accessible name; where the action is destructive enough to ask for
 * confirmation it keeps its words, inside a `Button`, with the icon leading them.
 *
 * The trashcan is drawn inline in `currentColor`, so it takes the variant's color
 * and the surrounding font size without an icon library.
 */
import type { JSX, ReactNode } from 'react';

import { Button } from './Button';
import type { ButtonProps } from './Button';
import { IconButton } from './IconButton';
import { TrashcanIcon } from './icons';

/**
 * The size of the trashcan beside words.
 *
 * A bare trashcan is the whole control and stands at the shared icon size; one
 * that leads words is punctuation before them, so it matches the cap height of
 * the text rather than overtopping it.
 */
const WORDED_ICON_SIZE = '1em';

interface DeleteButtonBaseProps extends Omit<ButtonProps, 'children'> {
  /** The accessible name, e.g. "Remove N12345" or "Delete this DART". */
  label: string;
}

/** A trashcan followed by words, inside a `Button` the caller can style. */
export interface WordedDeleteButtonProps extends DeleteButtonBaseProps {
  /** The words shown after the icon. */
  children: ReactNode;
}

/** A bare trashcan, with no frame for `variant` or `small` to act on. */
export interface IconDeleteButtonProps extends Omit<DeleteButtonBaseProps, 'variant' | 'small'> {
  children?: undefined;
  /** There is no frame without words, so the frame props are not accepted. */
  variant?: never;
  /** There is no frame without words, so the frame props are not accepted. */
  small?: never;
}

export type DeleteButtonProps = WordedDeleteButtonProps | IconDeleteButtonProps;

/**
 * A trashcan button that removes or deletes something.
 *
 * `label` names the thing being removed.  Without `children` the control is an
 * `IconButton`: a bare trashcan whose accessible name and tooltip are both
 * `label`, unless the caller passes its own `title` -- the reason the button is
 * disabled, say -- which wins.  That form has no frame, so it takes neither
 * `variant` nor `small`; passing either without children is a type error.
 * Children that are absent, `null` or `false` count as no children, so a caller
 * may show its words conditionally and still have a named control.  With
 * `children` the words follow the icon inside a `Button`, `label` is not repeated
 * as an `aria-label`, and there is no tooltip unless the caller supplies one,
 * since the button already says what it does; `variant` defaults to `quiet`, the
 * size to small, and the trashcan is drawn at the text size rather than at the
 * larger size a bare icon uses.  Every other `Button` prop -- `onClick`,
 * `disabled`, `type` -- is passed straight through either way.
 */
export function DeleteButton(props: DeleteButtonProps): JSX.Element {
  const { label, children, variant, small, className, title, ...rest } = props;
  // A caller that shows its words conditionally passes `false` or `null` for the
  // quiet case, so an empty child has to count as no child: otherwise the button
  // would draw the trashcan alone with no accessible name at all.
  const isIconOnly = children === undefined || children === null || children === false;
  if (isIconOnly) {
    return (
      <IconButton icon="trashcan" label={label} className={className} title={title} {...rest} />
    );
  }
  return (
    <Button
      variant={variant ?? 'quiet'}
      small={small ?? true}
      className={className}
      title={title}
      {...rest}
    >
      <TrashcanIcon size={WORDED_ICON_SIZE} />
      {children}
    </Button>
  );
}
