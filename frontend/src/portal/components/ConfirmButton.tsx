/**
 * A button that asks before it acts.
 *
 * The first press opens a small panel in its place: the caller's explanation, one
 * button per way to go ahead, and **Cancel**. Only a press in the panel acts. Most
 * actions offer one way to go ahead; making somebody a friend whose renewal carries a
 * contribution offers two (keep it, or stop it), which is why `choices` is a list.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX, KeyboardEvent, ReactNode } from 'react';

import { Button } from './Button';
import type { ButtonVariant } from './Button';

/** One way to go ahead from the confirmation panel. */
export interface ConfirmChoice {
  /** The button's words, e.g. "Deactivate account". */
  label: string;
  /** The button's look; `primary` unless given. */
  variant?: ButtonVariant;
  /**
   * Does the work. The panel closes once the promise resolves and stays open, for
   * the caller to show why, when it rejects.
   */
  onChoose: () => Promise<unknown>;
}

export interface ConfirmButtonProps {
  /** The button's words, and the accessible name of the panel it opens. */
  label: string;
  /** The button's look before it is pressed; `secondary` unless given. */
  variant?: ButtonVariant;
  disabled?: boolean;
  /** What the panel says before the choices: what will happen, and to whom. */
  children: ReactNode;
  /** The ways to go ahead, in the order the panel shows them. */
  choices: ConfirmChoice[];
}

/**
 * A button that opens a confirmation panel, and acts only from the panel.
 *
 * Every button in the panel is disabled while a choice is in flight. **Cancel** closes
 * the panel without calling anything.  Opening the panel moves the focus to its first
 * choice; **Cancel** and the Escape key close it and put the focus back on the button
 * that opened it, so a keyboard reader never loses their place.
 */
export function ConfirmButton({
  label,
  variant = 'secondary',
  disabled = false,
  children,
  choices,
}: ConfirmButtonProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstChoiceRef = useRef<HTMLButtonElement>(null);
  // Set when the panel is closed without acting, so the focus goes back to the trigger.
  const shouldRefocusTriggerRef = useRef(false);

  useEffect(() => {
    if (isOpen) {
      firstChoiceRef.current?.focus();
      return;
    }
    if (shouldRefocusTriggerRef.current) {
      shouldRefocusTriggerRef.current = false;
      triggerRef.current?.focus();
    }
  }, [isOpen]);

  const handleClose = (): void => {
    shouldRefocusTriggerRef.current = true;
    setIsOpen(false);
  };

  // The Escape key is a shortcut for Cancel from any button in the panel.
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>): void => {
    if (event.key !== 'Escape' || isPending) return;
    event.stopPropagation();
    handleClose();
  };

  if (!isOpen) {
    return (
      <Button
        ref={triggerRef}
        variant={variant}
        disabled={disabled}
        onClick={() => setIsOpen(true)}
      >
        {label}
      </Button>
    );
  }

  const handleChoose = (choice: ConfirmChoice): void => {
    setIsPending(true);
    void choice
      .onChoose()
      .then(
        () => setIsOpen(false),
        () => undefined,
      )
      .finally(() => setIsPending(false));
  };

  return (
    <section className="stack-tight" aria-label={label}>
      {children}
      <div className="cluster">
        {choices.map((choice, index) => (
          <Button
            ref={index === 0 ? firstChoiceRef : undefined}
            key={choice.label}
            onKeyDown={handleKeyDown}
            variant={choice.variant ?? 'primary'}
            disabled={isPending}
            onClick={() => handleChoose(choice)}
          >
            {choice.label}
          </Button>
        ))}
        <Button
          variant="quiet"
          disabled={isPending}
          onClick={handleClose}
          onKeyDown={handleKeyDown}
        >
          Cancel
        </Button>
      </div>
    </section>
  );
}
