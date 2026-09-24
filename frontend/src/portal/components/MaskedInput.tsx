import type { ChangeEvent, InputHTMLAttributes, JSX } from 'react';

import { caretAfterMask } from '@/portal/masks';

export interface MaskedInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'value' | 'onChange'
> {
  value: string;
  /** Run on every keystroke and on a paste; its answer is what the field holds. */
  mask: (raw: string) => string;
  onValueChange: (next: string) => void;
}

/**
 * A text input that can only hold what its mask allows.
 *
 * The mask runs before anything reaches the screen, so a character that does
 * not belong in the field is never shown and never submitted, and punctuation
 * the stored format needs is written as the value is typed.  The caret is put
 * back where the typist left it, so an edit in the middle of a number does not
 * jump to the end.
 *
 * @param value - the masked value; the component holds no state of its own.
 * @param onValueChange - called with the masked value whenever it changes.
 */
export function MaskedInput({
  value,
  mask,
  onValueChange,
  ...rest
}: MaskedInputProps): JSX.Element {
  const handleChange = (event: ChangeEvent<HTMLInputElement>): void => {
    const input = event.target;
    const raw = input.value;
    const caret = input.selectionStart ?? raw.length;
    const masked = mask(raw);
    // React re-renders with the same string it already has, so the DOM value
    // and the caret are set here rather than left where the browser put them.
    input.value = masked;
    const next = caretAfterMask(raw, caret, masked);
    input.setSelectionRange(next, next);
    onValueChange(masked);
  };

  return <input {...rest} value={value} onChange={handleChange} />;
}
