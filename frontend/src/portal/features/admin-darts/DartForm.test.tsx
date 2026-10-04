import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { DartForm, emptyDartValues } from './DartForm';

/** The add form, with whatever server errors a test hands it. */
function renderForm(errors: Record<string, string> = {}, serverError: unknown = null) {
  const handleSubmit = vi.fn();
  const handleCancel = vi.fn();
  const view = renderWithProviders(
    <DartForm
      initial={{ ...emptyDartValues(), name: 'Palo Alto', airport_identifiers: 'PAO' }}
      submitLabel="Add DART"
      errors={errors}
      serverError={serverError}
      onSubmit={handleSubmit}
      onCancel={handleCancel}
    />,
  );
  return { ...view, handleSubmit };
}

/** The DART's own Name box; each person's is named after its row. */
function dartName(): HTMLElement {
  return screen.getByRole('textbox', { name: 'Name' });
}

describe('DartForm contact boxes', () => {
  it.each(['Name', 'Title', 'Phone', 'Email'])(
    "names each person's %s box after its row, so no two boxes share a name",
    (label) => {
      renderForm();
      expect(screen.getByRole('textbox', { name: `${label} of person 1` })).toBeInTheDocument();
    },
  );
});

describe('DartForm', () => {
  it('moves the focus to the first field it refuses', async () => {
    renderForm();
    await userEvent.clear(dartName());
    await userEvent.click(screen.getByRole('button', { name: 'Add DART' }));

    expect(dartName()).toHaveFocus();
  });

  it('says beside the button how many fields to check after a refused save', async () => {
    renderForm();
    await userEvent.clear(dartName());
    await userEvent.clear(screen.getByRole('textbox', { name: /Airports/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Add DART' }));

    expect(screen.getByRole('status')).toHaveTextContent('Check the 2 highlighted fields.');
  });

  it('clears the missing-name complaint as soon as a name is typed', async () => {
    renderForm();
    await userEvent.clear(dartName());
    await userEvent.click(screen.getByRole('button', { name: 'Add DART' }));
    await userEvent.type(dartName(), 'N');

    expect(screen.queryByText('Give the DART a name.')).toBeNull();
  });

  it("clears the server's complaint about a field once the field is edited", async () => {
    renderForm({ name: 'A DART with that name already exists.' }, new Error('refused'));
    await userEvent.type(dartName(), ' North');

    expect(screen.queryByText('A DART with that name already exists.')).toBeNull();
  });

  it('moves the focus to the field the server refused', () => {
    renderForm({ name: 'A DART with that name already exists.' }, new Error('refused'));

    expect(dartName()).toHaveFocus();
  });
});
