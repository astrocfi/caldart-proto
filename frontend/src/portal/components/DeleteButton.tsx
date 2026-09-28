/**
 * The portal's one Remove-or-Delete control: a trashcan, sometimes with words.
 *
 * Every screen that used to spell "Remove" or "Delete" on a button uses this
 * instead, so one icon means one thing wherever it appears. Where the control
 * sits in a row or on a form line it is a bare trashcan and `label` is the whole
 * of its accessible name; where it wants more weight it keeps its words, inside a
 * `Button`, with the icon leading them. Every delete asks first: give it
 * `onDelete` and the first press swaps the control, in place, for a small danger
 * button reading `confirmLabel` beside a plain **Keep**, and only that
 * confirmation calls `onDelete`. A caller whose own flow already confirms the
 * action -- a typed value, a separate warning screen -- leaves `onDelete` out,
 * and the control fires its ordinary click at once, as it always has.
 *
 * The trashcan is drawn inline in `currentColor`, so it takes the variant's color
 * and the surrounding font size without an icon library.
 */
import { useCallback, useRef, useState } from 'react';
import type { FocusEvent, JSX, ReactNode } from 'react';

import { Button } from './Button';
import type { ButtonProps } from './Button';
import { IconButton } from './IconButton';
import { TrashcanIcon } from './icons';
import { useClickOutside } from './useClickOutside';

/** The size of the trashcan beside words. */
const WORDED_ICON_SIZE = '1em';

/** The confirmation's danger button, unless the caller names its own. */
const DEFAULT_CONFIRM_LABEL = 'Delete';

/** What the confirmation's second button always reads. */
const KEEP_LABEL = 'Keep';

interface DeleteButtonBaseProps extends Omit<ButtonProps, 'children'> {
  /** The accessible name, e.g. "Remove N12345" or "Delete this DART". */
  label: string;
  /**
   * Called once the reader accepts the inline confirmation, from the danger
   * button in the pair that replaces this control. It may return a promise;
   * the control reverts to its ordinary self once it settles, whichever way.
   * Left out, the control has no confirmation of its own and fires its click
   * straight away, for a caller whose own flow already confirms the action.
   */
  onDelete?: () => void | Promise<unknown>;
  /** The confirmation's danger button, once `onDelete` is given. Defaults to "Delete". */
  confirmLabel?: string;
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
 * A trashcan button that removes or deletes something, and asks first.
 *
 * `label` names the thing being removed. Without `children` the control is an
 * `IconButton`: a bare trashcan whose accessible name and tooltip are both
 * `label`, unless the caller passes its own `title` -- the reason the button is
 * disabled, say -- which wins. That form has no frame, so it takes neither
 * `variant` nor `small`; passing either without children is a type error.
 * Children that are absent, `null` or `false` count as no children, so a caller
 * may show its words conditionally and still have a named control. With
 * `children` the words follow the icon inside a `Button`, `label` is not repeated
 * as an `aria-label`, and there is no tooltip unless the caller supplies one,
 * since the button already says what it does; `variant` defaults to `quiet`, the
 * size to small, and the trashcan is drawn at the text size rather than at the
 * larger size a bare icon uses.
 *
 * Given `onDelete`, the first press swaps the whole control, in place, for a
 * `role="group"` pair named by `label`: a small danger button reading
 * `confirmLabel` and a plain **Keep**. Only the danger button calls `onDelete`;
 * pressing **Keep**, pressing Escape, clicking outside the pair, or moving the
 * focus off it all restore the trashcan without calling anything. The pair
 * disables both of its buttons while `onDelete`'s promise is in flight, and
 * while the caller's own `disabled` is true. Every other `Button` prop --
 * `type`, `aria-*`, a caller's own `onClick` used when `onDelete` is left out --
 * reaches whichever control is on screen.
 */
export function DeleteButton(props: DeleteButtonProps): JSX.Element {
  const {
    label,
    children,
    variant,
    small,
    className,
    title,
    onDelete,
    confirmLabel = DEFAULT_CONFIRM_LABEL,
    disabled = false,
    ...rest
  } = props;

  const [isConfirming, setIsConfirming] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);

  const handleKeep = useCallback((): void => setIsConfirming(false), []);
  useClickOutside(containerRef, handleKeep, isConfirming);

  // Tabbing away is not a click, so `useClickOutside`'s pointerdown listener
  // never sees it; a plain blur that lands outside the pair closes it the
  // same way.
  const handleBlur = (event: FocusEvent<HTMLSpanElement>): void => {
    const next = event.relatedTarget;
    if (next instanceof Node && containerRef.current?.contains(next) === true) return;
    handleKeep();
  };

  const handleConfirm = (): void => {
    setIsPending(true);
    void Promise.resolve(onDelete?.())
      .catch(() => undefined)
      .finally(() => {
        setIsPending(false);
        setIsConfirming(false);
      });
  };

  if (onDelete !== undefined && isConfirming) {
    return (
      <span
        ref={containerRef}
        role="group"
        aria-label={label}
        className="cluster"
        onBlur={handleBlur}
      >
        <Button variant="danger" small onClick={handleConfirm} disabled={disabled || isPending}>
          {confirmLabel}
        </Button>
        <Button variant="quiet" small onClick={handleKeep} disabled={disabled || isPending}>
          {KEEP_LABEL}
        </Button>
      </span>
    );
  }

  const handleReveal = onDelete !== undefined ? (): void => setIsConfirming(true) : undefined;
  const isIconOnly = children === undefined || children === null || children === false;

  if (isIconOnly) {
    return (
      <IconButton
        icon="trashcan"
        label={label}
        className={className}
        title={title}
        disabled={disabled}
        {...rest}
        onClick={handleReveal ?? rest.onClick}
      />
    );
  }
  return (
    <Button
      variant={variant ?? 'quiet'}
      small={small ?? true}
      className={className}
      title={title}
      disabled={disabled}
      {...rest}
      onClick={handleReveal ?? rest.onClick}
    >
      <TrashcanIcon size={WORDED_ICON_SIZE} />
      {children}
    </Button>
  );
}
