import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { maskNNumber, maskPhone } from '@/portal/masks';
import { MaskedInput } from './MaskedInput';

function Harness({ mask, initial = '' }: { mask: (raw: string) => string; initial?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <label htmlFor="masked">Field</label>
      <MaskedInput id="masked" value={value} mask={mask} onValueChange={(next) => setValue(next)} />
    </>
  );
}

const field = (): HTMLInputElement => screen.getByLabelText('Field');

function renderMasked(mask: (raw: string) => string, initial = ''): void {
  render(<Harness mask={mask} initial={initial} />);
}

describe('MaskedInput', () => {
  it('writes the dashes of a phone number as it is typed', async () => {
    const user = userEvent.setup();
    renderMasked(maskPhone);

    await user.type(field(), '4155550100');

    expect(field().value).toBe('415-555-0100');
  });

  it('never lets a letter into a phone number', async () => {
    const user = userEvent.setup();
    renderMasked(maskPhone);

    await user.type(field(), '415abc555');

    expect(field().value).toBe('415-555');
  });

  it('stops at ten digits however many are typed', async () => {
    const user = userEvent.setup();
    renderMasked(maskPhone);

    await user.type(field(), '415555010099');

    expect(field().value).toBe('415-555-0100');
  });

  it('writes the N of a registration for the typist', async () => {
    const user = userEvent.setup();
    renderMasked(maskNNumber);

    await user.type(field(), '172sp');

    expect(field().value).toBe('N172SP');
  });

  it('leaves the caret where an edit in the middle was made', async () => {
    const user = userEvent.setup();
    renderMasked(maskPhone, '415-555-0100');

    const input = field();
    input.setSelectionRange(1, 1);
    await user.type(input, '9', { initialSelectionStart: 1, initialSelectionEnd: 1 });

    expect(field().value).toBe('491-555-5010');
    expect(field().selectionStart).toBe(2);
  });
});
