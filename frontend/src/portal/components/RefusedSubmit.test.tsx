import { render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { describe, expect, it } from 'vitest';

import { Field } from './Field';
import { RefusedSubmitNote, useFreshErrors, useRefusedSubmit } from './RefusedSubmit';

/** A long form whose own rule needs both names, with the submit button at its foot. */
function NamesForm(): JSX.Element {
  const [first, setFirst] = useState('');
  const [last, setLast] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef);
  const firstError = isSubmitted && first === '' ? 'Give a first name.' : null;
  const lastError = isSubmitted && last === '' ? 'Give a last name.' : null;

  const handleSubmit = (event: FormEvent): void => {
    event.preventDefault();
    setIsSubmitted(true);
    if (first === '' || last === '') refusal.refuse();
  };

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate>
      <Field label="First name" error={firstError}>
        {(props) => (
          <input {...props} value={first} onChange={(event) => setFirst(event.target.value)} />
        )}
      </Field>
      <Field label="Last name" error={lastError}>
        {(props) => (
          <input {...props} value={last} onChange={(event) => setLast(event.target.value)} />
        )}
      </Field>
      <button type="submit">Save</button>
      <RefusedSubmitNote count={refusal.count} />
    </form>
  );
}

/** A form whose only complaint comes from the server, about the email address. */
function ServerRefusedForm({ error }: { error: Error | null }): JSX.Element {
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, error);
  return (
    <form ref={formRef}>
      <Field label="Email" error={error === null ? null : 'Enter a valid email address.'}>
        {(props) => <input {...props} />}
      </Field>
      <button type="submit">Save</button>
      <RefusedSubmitNote count={refusal.count} />
    </form>
  );
}

describe('useRefusedSubmit', () => {
  it('moves the focus to the first highlighted field after a refused submit', async () => {
    render(<NamesForm />);

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(screen.getByRole('textbox', { name: 'First name' })).toHaveFocus();
  });

  it('says beside the button how many fields to check', async () => {
    render(<NamesForm />);

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(screen.getByRole('status')).toHaveTextContent('Check the 2 highlighted fields.');
  });

  it('counts down as the highlighted fields are corrected', async () => {
    render(<NamesForm />);

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    await userEvent.type(screen.getByRole('textbox', { name: 'First name' }), 'Ada');

    expect(await screen.findByText('Check the highlighted field.')).toBeInTheDocument();
  });

  it('drops the line once every field is corrected', async () => {
    render(<NamesForm />);

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    await userEvent.type(screen.getByRole('textbox', { name: 'First name' }), 'Ada');
    await userEvent.type(screen.getByRole('textbox', { name: 'Last name' }), 'Lovelace');

    expect(screen.queryByRole('status')).toBeNull();
  });

  it('moves the focus to the field the server refused', () => {
    const { rerender } = render(<ServerRefusedForm error={null} />);
    rerender(<ServerRefusedForm error={new Error('refused')} />);

    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveFocus();
  });

  it('says nothing before any submit is refused', () => {
    render(<ServerRefusedForm error={null} />);

    expect(screen.queryByRole('status')).toBeNull();
  });
});

describe('RefusedSubmitNote', () => {
  it('names one field in the singular', () => {
    render(<RefusedSubmitNote count={1} />);

    expect(screen.getByRole('status')).toHaveTextContent('Check the highlighted field.');
  });

  it('draws nothing for no fields', () => {
    const { container } = render(<RefusedSubmitNote count={0} />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe('useFreshErrors', () => {
  const ERROR = new Error('refused');
  const ERRORS = { email: 'Enter a valid email address.', detail: 'Not saved.' };

  it('keeps every error while the fields are as they were', () => {
    const { result } = renderHook(() => useFreshErrors(ERROR, { email: 'ada@' }, ERRORS));

    expect(result.current).toEqual(ERRORS);
  });

  it('drops the error for a field edited since the errors arrived', () => {
    const { result, rerender } = renderHook(
      ({ email }) => useFreshErrors(ERROR, { email }, ERRORS),
      { initialProps: { email: 'ada@' } },
    );
    rerender({ email: 'ada@example.org' });

    expect(result.current).toEqual({ detail: 'Not saved.' });
  });

  it('shows the errors of a new refusal again', () => {
    const { result, rerender } = renderHook(
      ({ email, error }) => useFreshErrors(error, { email }, ERRORS),
      { initialProps: { email: 'ada@', error: ERROR } },
    );
    rerender({ email: 'ada@example', error: ERROR });
    rerender({ email: 'ada@example', error: new Error('refused again') });

    expect(result.current).toEqual(ERRORS);
  });

  it('keeps every error for a caller that does not say where they came from', () => {
    const { result, rerender } = renderHook(
      ({ email }) => useFreshErrors(undefined, { email }, ERRORS),
      { initialProps: { email: 'ada@' } },
    );
    rerender({ email: 'ada@example.org' });

    expect(result.current).toEqual(ERRORS);
  });
});
