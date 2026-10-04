/**
 * A button that asks before it acts.
 *
 * The first press opens a small panel below the row the button sits in: the caller's
 * explanation, one button per way to go ahead, and **Cancel**. Only a press in the
 * panel acts. Most actions offer one way to go ahead; making somebody a friend whose
 * renewal carries a contribution offers two (keep it, or stop it), which is why
 * `choices` is a list.
 *
 * `ConfirmButton` is the portal's one confirmation for an action that cannot be undone,
 * other than a delete, which is `DeleteButton`'s. A destructive choice is drawn red
 * (`variant: 'danger'`) and names the act, and the way out always reads **Cancel**.
 */
import { useEffect, useId, useRef, useState } from 'react';
import type { JSX, KeyboardEvent, ReactNode } from 'react';

import { Button } from './Button';
import type { ButtonVariant } from './Button';
import { rememberPlace, useRefocusOnUnmount } from './focus';

/** One way to go ahead from the confirmation panel. */
export interface ConfirmChoice {
  /** The button's words, which name the act, e.g. "Deactivate account". */
  label: string;
  /** The button's look; `primary` unless given, and `danger` for a destructive act. */
  variant?: ButtonVariant;
  /** Hold the button back, say while the panel waits on what it has to ask. */
  disabled?: boolean;
  /**
   * Does the work. The panel closes once the promise resolves and stays open, for
   * the caller to show why, when it rejects.
   */
  onChoose: () => Promise<unknown>;
}

export interface ConfirmButtonProps {
  /** The button's words, and the accessible name of the panel it opens. */
  label: string;
  /** The button's look; `secondary` unless given. */
  variant?: ButtonVariant;
  /** Draw the button and the panel's buttons small, to sit among small ones. */
  small?: boolean;
  disabled?: boolean;
  /** What the panel says before the choices: what will happen, and to whom. */
  children?: ReactNode;
  /** The ways to go ahead, in the order the panel shows them. */
  choices: ConfirmChoice[];
}

/** What the panel's way out always reads. */
const CANCEL_LABEL = 'Cancel';

/**
 * A button that opens a confirmation panel, and acts only from the panel.
 *
 * The button stays where it is while the panel is open, marked `aria-expanded`, and
 * pressing it again closes the panel. The panel (a region named by `label`) sits
 * after the button and, inside a wrapping row such as `.cluster`, takes a line of its
 * own at full width below the row, so the buttons around it stay in place.
 *
 * Every button in the panel is disabled while a choice is in flight. **Cancel** closes
 * the panel without calling anything. Opening the panel moves the focus to its first
 * choice or, when that choice is `danger`, to **Cancel**, so a stray second Enter
 * does nothing it cannot take back; **Cancel** and the Escape key close it and put the focus back on the button
 * that opened it, and an Escape pressed in the panel goes no further, so a panel the
 * button sits in stays open. After a choice goes through the focus also returns to
 * the button or, when the change took the button away, to the nearest place still on
 * the page: the table cell or list item it sat in, or the heading of its card.
 */
export function ConfirmButton({
  label,
  variant = 'secondary',
  small = false,
  disabled = false,
  children,
  choices,
}: ConfirmButtonProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstChoiceRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  // Set when the panel closes, so the focus goes back to the trigger (or near it).
  const shouldRefocusRef = useRef(false);
  const placeRef = useRef<(() => HTMLElement | null) | null>(null);
  const hasChosenRef = useRef(false);
  useRefocusOnUnmount(placeRef, hasChosenRef);

  const isFirstChoiceDanger = choices[0]?.variant === 'danger';

  useEffect(() => {
    if (isOpen) {
      // A destructive first choice waits for a deliberate press: a stray second Enter
      // lands on Cancel, as it does in `DeleteButton`.
      (isFirstChoiceDanger ? cancelRef : firstChoiceRef).current?.focus();
      return;
    }
    if (shouldRefocusRef.current) {
      shouldRefocusRef.current = false;
      placeRef.current?.()?.focus();
    }
  }, [isOpen, isFirstChoiceDanger]);

  const handleOpen = (): void => {
    placeRef.current = rememberPlace(triggerRef.current);
    setIsOpen(true);
  };

  const handleClose = (): void => {
    shouldRefocusRef.current = true;
    setIsOpen(false);
  };

  const handleToggle = (): void => (isOpen ? handleClose() : handleOpen());

  // The Escape key is a shortcut for Cancel from any button in the panel.
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>): void => {
    if (event.key !== 'Escape' || isPending) return;
    event.stopPropagation();
    event.preventDefault();
    handleClose();
  };

  const handleChoose = (choice: ConfirmChoice): void => {
    // Armed before the work starts: a change that takes this button away may land
    // before the promise does.
    hasChosenRef.current = true;
    setIsPending(true);
    void choice
      .onChoose()
      .then(handleClose, () => undefined)
      .finally(() => setIsPending(false));
  };

  return (
    <>
      <Button
        ref={triggerRef}
        variant={variant}
        small={small}
        disabled={disabled}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
        onClick={handleToggle}
      >
        {label}
      </Button>
      {isOpen ? (
        <section
          id={panelId}
          className="confirm-panel stack-tight"
          aria-label={label}
          data-own-escape
        >
          {children}
          <div className="cluster">
            {choices.map((choice, index) => (
              <Button
                ref={index === 0 ? firstChoiceRef : undefined}
                key={choice.label}
                onKeyDown={handleKeyDown}
                variant={choice.variant ?? 'primary'}
                small={small}
                disabled={isPending || choice.disabled === true}
                onClick={() => handleChoose(choice)}
              >
                {choice.label}
              </Button>
            ))}
            <Button
              ref={cancelRef}
              variant="quiet"
              small={small}
              disabled={isPending}
              onClick={handleClose}
              onKeyDown={handleKeyDown}
            >
              {CANCEL_LABEL}
            </Button>
          </div>
        </section>
      ) : null}
    </>
  );
}
