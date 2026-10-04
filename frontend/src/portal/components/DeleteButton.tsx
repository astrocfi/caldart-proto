/**
 * The portal's one Remove-or-Delete control: a trashcan, sometimes with words.
 *
 * Every screen that used to spell "Remove" or "Delete" on a button uses this
 * instead, so one icon means one thing wherever it appears. Where the control
 * sits in a row or on a form line it is a bare trashcan and `label` is the whole
 * of its accessible name; where it wants more weight it keeps its words, inside a
 * `Button`, with the icon leading them. Every delete asks first: give it
 * `onDelete` and the first press swaps the control, in place, for a small danger
 * button reading `confirmLabel` beside a plain **Cancel**, and only that
 * confirmation calls `onDelete`.  `DeleteButton` is the portal's one confirmation
 * for a delete; every other action that cannot be undone asks through
 * `ConfirmButton`, with the same **Cancel**. A caller whose own flow already confirms the
 * action -- a typed value, a separate warning screen -- leaves `onDelete` out,
 * and the control fires its ordinary click at once, as it always has.
 *
 * The trashcan is drawn inline in `currentColor`, so it takes the variant's color
 * and the surrounding font size without an icon library.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FocusEvent, JSX, ReactNode } from 'react';

import { Button } from './Button';
import type { ButtonProps } from './Button';
import { IconButton } from './IconButton';
import { rememberPlace, useRefocusOnUnmount } from './focus';
import { TrashcanIcon } from './icons';
import { useClickOutside } from './useClickOutside';

/** The size of the trashcan beside words. */
const WORDED_ICON_SIZE = '1em';

/** The confirmation's danger button, unless the caller names its own. */
const DEFAULT_CONFIRM_LABEL = 'Delete';

/** What the confirmation's second button always reads. */
const CANCEL_LABEL = 'Cancel';

interface DeleteButtonBaseProps extends Omit<ButtonProps, 'children' | 'ref'> {
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
  /**
   * What the delete will take with it, said before the confirmation's buttons, such
   * as "It will disappear from every member's profile."  Left out, the pair stands
   * alone, which suits a row's trashcan.
   */
  warning?: ReactNode;
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
 * `confirmLabel` and a plain **Cancel**, after the `warning` when there is one.
 * Only the danger button calls `onDelete`; pressing **Cancel**, pressing Escape,
 * clicking outside the pair, or moving the focus off it all restore the trashcan
 * without calling anything. The focus moves to **Cancel** when the pair opens, so a
 * stray second Enter keeps the thing, and returns to the trashcan after **Cancel**
 * or Escape. Once a delete settles the focus goes back to the trashcan or, when the
 * delete took it away with its row, to the nearest place still on the page: the
 * table cell or list item it sat in, or the heading of its card. An Escape pressed
 * on the pair stops there, so a panel or dialog the control sits in stays open. The pair
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
    warning,
    disabled = false,
    ...rest
  } = props;

  const [isConfirming, setIsConfirming] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Set by Cancel, Escape, and a settled delete, the ways out that leave the reader
  // where they were; a click elsewhere or a tab away has already put the focus
  // somewhere of its own.
  const shouldRefocusTriggerRef = useRef(false);
  const placeRef = useRef<(() => HTMLElement | null) | null>(null);
  const hasDeletedRef = useRef(false);
  useRefocusOnUnmount(placeRef, hasDeletedRef);

  const handleDismiss = useCallback((): void => setIsConfirming(false), []);
  const handleCancel = useCallback((): void => {
    shouldRefocusTriggerRef.current = true;
    setIsConfirming(false);
  }, []);
  useClickOutside(containerRef, handleDismiss, isConfirming);

  useEffect(() => {
    if (isConfirming) {
      cancelRef.current?.focus();
      return undefined;
    }
    if (shouldRefocusTriggerRef.current) {
      shouldRefocusTriggerRef.current = false;
      // The trashcan drawn again after the pair is a new element, so it comes first;
      // the remembered place stands in while it is disabled.
      const trigger = triggerRef.current;
      (trigger !== null && !trigger.disabled ? trigger : (placeRef.current?.() ?? null))?.focus();
    }
    return undefined;
  }, [isConfirming]);

  // A native listener on the pair, so the key stops here, before it bubbles to a
  // panel around the control: `usePanelFocus`'s listener on the panel's element, or a
  // popover's listener on the document, would close that panel too.  The pair's
  // `data-own-escape` tells `usePanelFocus` the same thing should the key get past.
  useEffect(() => {
    const container = containerRef.current;
    if (!isConfirming || container === null) return undefined;
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      event.preventDefault();
      handleCancel();
    };
    container.addEventListener('keydown', handleKeyDown);
    return () => container.removeEventListener('keydown', handleKeyDown);
  }, [isConfirming, handleCancel]);

  // Tabbing away is not a click, so `useClickOutside`'s pointerdown listener
  // never sees it; a plain blur that lands outside the pair closes it the
  // same way.
  const handleBlur = (event: FocusEvent<HTMLSpanElement>): void => {
    const next = event.relatedTarget;
    if (next instanceof Node && containerRef.current?.contains(next) === true) return;
    handleDismiss();
  };

  const handleConfirm = (): void => {
    // Armed before the delete starts: the row may go before the promise settles.
    hasDeletedRef.current = true;
    setIsPending(true);
    void Promise.resolve(onDelete?.())
      .catch(() => undefined)
      .finally(() => {
        shouldRefocusTriggerRef.current = true;
        setIsPending(false);
        setIsConfirming(false);
      });
  };

  if (onDelete !== undefined && isConfirming) {
    const buttons = (
      <>
        <Button variant="danger" small onClick={handleConfirm} disabled={disabled || isPending}>
          {confirmLabel}
        </Button>
        <Button
          ref={cancelRef}
          variant="quiet"
          small
          onClick={handleCancel}
          disabled={disabled || isPending}
        >
          {CANCEL_LABEL}
        </Button>
      </>
    );
    return (
      <span
        ref={containerRef}
        role="group"
        aria-label={label}
        className={warning === undefined ? 'cluster' : 'delete-confirm stack-tight'}
        data-own-escape
        onBlur={handleBlur}
      >
        {warning === undefined ? (
          buttons
        ) : (
          <>
            <span className="delete-confirm__warning">{warning}</span>
            <span className="cluster">{buttons}</span>
          </>
        )}
      </span>
    );
  }

  const handleReveal =
    onDelete !== undefined
      ? (): void => {
          placeRef.current = rememberPlace(triggerRef.current);
          setIsConfirming(true);
        }
      : undefined;
  const isIconOnly = children === undefined || children === null || children === false;

  if (isIconOnly) {
    return (
      <IconButton
        ref={triggerRef}
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
      ref={triggerRef}
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
