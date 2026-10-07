import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { maskExtension, maskNNumber, maskPhone, maskPostalCode } from '@/portal/masks';
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

  it('leaves the caret in place when a letter is typed mid-number', async () => {
    const user = userEvent.setup();
    renderMasked(maskPhone, '415-555-0100');

    await user.type(field(), 'x7', { initialSelectionStart: 6, initialSelectionEnd: 6 });

    expect(field().value).toBe('415-557-5010');
  });

  it('leaves the caret at the start of a selection a refused letter replaced', async () => {
    const user = userEvent.setup();
    renderMasked(maskPhone, '415-555-0100');

    await user.type(field(), 'x', { initialSelectionStart: 5, initialSelectionEnd: 7 });

    expect(field().selectionStart).toBe(5);
  });

  it('leaves the caret in place when an extension refuses a letter', async () => {
    const user = userEvent.setup();
    renderMasked(maskExtension, '4021');

    await user.type(field(), 'x9', { initialSelectionStart: 2, initialSelectionEnd: 2 });

    expect(field().value).toBe('40921');
  });

  it('leaves the caret in place when a ZIP code refuses a letter', async () => {
    const user = userEvent.setup();
    renderMasked(maskPostalCode, '9535');

    await user.type(field(), 'x0', { initialSelectionStart: 2, initialSelectionEnd: 2 });

    expect(field().value).toBe('95035');
  });

  it('moves the caret past a letter a registration keeps', async () => {
    const user = userEvent.setup();
    renderMasked(maskNNumber, 'N172P');

    await user.type(field(), 'S', { initialSelectionStart: 4, initialSelectionEnd: 4 });

    expect(field().selectionStart).toBe(5);
  });
});
