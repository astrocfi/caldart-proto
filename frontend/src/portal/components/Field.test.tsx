import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Field } from '@/portal/components/Field';

/** Render a text box in a `Field` with `hint` and `error`. */
function renderField(error: string | null): HTMLElement {
  const { container } = render(
    <Field label="Phone" hint="10 digits, such as 415-555-0100" error={error}>
      {(props) => <input {...props} />}
    </Field>,
  );
  return container;
}

describe('Field', () => {
  it('puts the hint between the label and the box', () => {
    const container = renderField(null);
    const order = Array.from(container.querySelectorAll('label, .field__hint, input')).map(
      (node) => node.tagName.toLowerCase() + (node.className ? `.${node.className}` : ''),
    );
    expect(order).toEqual(['label.field__label', 'span.field__hint', 'input']);
  });

  it('describes the box by its hint', () => {
    renderField(null);
    expect(screen.getByRole('textbox', { name: 'Phone' })).toHaveAccessibleDescription(
      '10 digits, such as 415-555-0100',
    );
  });

  it('puts the error under the box', () => {
    const container = renderField('Enter 10 digits.');
    const input = container.querySelector('input');
    expect(input?.nextElementSibling).toBe(screen.getByRole('alert'));
  });

  it('hides the hint while the error shows', () => {
    renderField('Enter 10 digits.');
    expect(screen.getByText('10 digits, such as 415-555-0100')).not.toBeVisible();
  });

  it('keeps the hidden hint in its place, so the box does not move', () => {
    const container = renderField('Enter 10 digits.');
    const input = container.querySelector('input');
    expect(input?.previousElementSibling).toHaveTextContent('10 digits, such as 415-555-0100');
  });

  it('marks the hint hidden while an error shows, so one column gives its line up', () => {
    renderField('Enter 10 digits.');
    expect(screen.getByText('10 digits, such as 415-555-0100')).toHaveClass('field__hint--hidden');
  });

  it('adds words a screen reader hears after the label, for boxes that share one', () => {
    render(
      <Field label="Phone" labelSuffix=" of person 2">
        {(props) => <input {...props} />}
      </Field>,
    );
    expect(screen.getByRole('textbox', { name: 'Phone of person 2' })).toBeInTheDocument();
  });

  it('draws an empty hint slot for a field with no hint, so a grid row lines up', () => {
    const { container } = render(
      <Field label="Alternate phone">{(props) => <input {...props} />}</Field>,
    );
    const slot = container.querySelector('input')?.previousElementSibling;
    expect(slot).toHaveClass('field__hint-slot');
  });

  it('leaves the empty hint slot out of what a screen reader reads', () => {
    const { container } = render(
      <Field label="Alternate phone">{(props) => <input {...props} />}</Field>,
    );
    expect(container.querySelector('.field__hint-slot')).toHaveAttribute('aria-hidden', 'true');
  });

  it('describes the box by its error alone while it shows', () => {
    renderField('Enter 10 digits.');
    expect(screen.getByRole('textbox', { name: 'Phone' })).toHaveAccessibleDescription(
      'Enter 10 digits.',
    );
  });

  it('keeps a status under the box while the error shows', () => {
    const { container } = render(
      <Field label="Medical expires" status="Not yet verified" error="Enter a date.">
        {(props) => <input {...props} />}
      </Field>,
    );
    const input = container.querySelector('input');
    expect(input?.nextElementSibling).toHaveTextContent('Not yet verified');
    expect(screen.getByRole('textbox', { name: 'Medical expires' })).toHaveAccessibleDescription(
      'Enter a date. Not yet verified',
    );
  });
});
