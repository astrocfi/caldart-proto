/**
 * A button that asks before it acts.
 *
 * The first press opens a small panel in its place: the caller's explanation, one
 * button per way to go ahead, and **Cancel**. Only a press in the panel acts. Most
 * actions offer one way to go ahead; making somebody a friend whose renewal carries a
 * contribution offers two (keep it, or stop it), which is why `choices` is a list.
 */
import { useState } from 'react';
import type { JSX, ReactNode } from 'react';

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
 * the panel without calling anything.
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

  if (!isOpen) {
    return (
      <Button variant={variant} disabled={disabled} onClick={() => setIsOpen(true)}>
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
        {choices.map((choice) => (
          <Button
            key={choice.label}
            variant={choice.variant ?? 'primary'}
            disabled={isPending}
            onClick={() => handleChoose(choice)}
          >
            {choice.label}
          </Button>
        ))}
        <Button variant="quiet" disabled={isPending} onClick={() => setIsOpen(false)}>
          Cancel
        </Button>
      </div>
    </section>
  );
}
