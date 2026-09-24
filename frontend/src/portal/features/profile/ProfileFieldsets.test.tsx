import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { ProfileFieldsets } from './ProfileFieldsets';
import type { ProfileFieldsetsProps } from './ProfileFieldsets';
import { TEST_DARTS } from '@test/fixtures/profile';
import { EMPTY_PROFILE_FORM } from './form';

const CONTACT_LABELS = [
  'Phone',
  'Alternate phone',
  'Address',
  'Address line 2',
  'City',
  'State',
  'ZIP code',
  'California county',
  'Emergency contact',
  'Emergency contact phone',
];

const AVIATION_LABELS = [
  'Home airport',
  'Home airport city',
  'DART',
  'Air Care Alliance number',
  'Pilot certificate',
  'Certificate number',
  'IFR rated',
  'Medical',
  'Medical expires',
  'Last flight review',
  'Total hours',
];

const RATING_LABELS = [
  'ASEL',
  'AMEL',
  'ASES',
  'AMES',
  'Helicopter',
  'Instrument',
  'CFI',
  'CFII',
  'MEI',
];

const VOLUNTEER_LABELS = [
  'Mission pilot',
  'Ground team',
  'Exercises and training',
  'Member support',
  'Fundraising',
  'Social media',
  'Newsletter',
];

function renderFieldsets(overrides: Partial<ProfileFieldsetsProps> = {}) {
  const handleChange = vi.fn();
  renderWithProviders(
    <ProfileFieldsets
      value={EMPTY_PROFILE_FORM}
      onChange={handleChange}
      darts={TEST_DARTS}
      {...overrides}
    />,
  );
  return handleChange;
}

describe('<ProfileFieldsets/>', () => {
  it.each([...CONTACT_LABELS, ...AVIATION_LABELS, ...RATING_LABELS, ...VOLUNTEER_LABELS])(
    'renders the %s field',
    (label) => {
      renderFieldsets();
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    },
  );

  it.each(['Contact', 'Aviation', 'Ratings', 'Volunteer interests'])(
    'groups the fields under the %s legend',
    (legend) => {
      renderFieldsets();
      expect(screen.getByRole('group', { name: legend })).toBeInTheDocument();
    },
  );

  it('gives each of the three numbers an extension box beside it', () => {
    renderFieldsets();
    expect(screen.getAllByLabelText('ext.')).toHaveLength(3);
  });

  it('refuses a letter typed into a phone number', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.type(screen.getByLabelText('Phone'), 'a');

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ phone: '' }) as Partial<typeof EMPTY_PROFILE_FORM>,
    );
  });

  it('drops the ICAO K from a home airport as it is typed', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.type(screen.getByLabelText('Home airport'), 'K');

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        home_airport_identifier: '',
      }) as Partial<typeof EMPTY_PROFILE_FORM>,
    );
  });

  it('reports a typed character through onChange', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.type(screen.getByLabelText('City'), 'S');

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PROFILE_FORM, city: 'S' });
  });

  it('reports a chosen option through onChange', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.selectOptions(screen.getByLabelText('Pilot certificate'), 'private');

    expect(onChange).toHaveBeenCalledWith({
      ...EMPTY_PROFILE_FORM,
      pilot_certificate_type: 'private',
    });
  });

  it('picks the state from a list rather than taking two typed letters', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.selectOptions(screen.getByLabelText('State'), 'NV');

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PROFILE_FORM, state: 'NV' });
  });

  it("picks the county from California's, and offers an out for everyone else", async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();
    const county = screen.getByLabelText('California county');

    await user.selectOptions(county, 'Napa');

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PROFILE_FORM, county: 'Napa' });
    expect(within(county).getByRole('option', { name: 'Not in California' })).toBeInTheDocument();
  });

  it('offers the ratings in two rows, category and class then instructor', () => {
    renderFieldsets();

    for (const rating of ['ASEL', 'AMEL', 'ASES', 'AMES', 'Helicopter', 'Instrument']) {
      expect(screen.getByRole('checkbox', { name: rating })).toBeInTheDocument();
    }
    for (const rating of ['CFI', 'CFII', 'MEI']) {
      expect(screen.getByRole('checkbox', { name: rating })).toBeInTheDocument();
    }
    expect(screen.queryByRole('checkbox', { name: 'Glider' })).not.toBeInTheDocument();
  });

  it('puts Mission pilot first among the volunteer interests', () => {
    renderFieldsets();
    const interests = screen
      .getByRole('group', { name: 'Volunteer interests' })
      .querySelectorAll('.checkbox span');
    expect(interests[0]?.textContent).toBe('Mission pilot');
  });

  it('upper-cases the home airport identifier as it is typed', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.type(screen.getByLabelText('Home airport'), 'p');

    expect(onChange).toHaveBeenCalledWith({
      ...EMPTY_PROFILE_FORM,
      home_airport_identifier: 'P',
    });
  });

  it('adds a rating when its box is ticked', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.click(screen.getByLabelText('Instrument'));

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PROFILE_FORM, ratings: ['instrument'] });
  });

  it('drops a rating when its box is cleared', async () => {
    const user = userEvent.setup();
    const value = { ...EMPTY_PROFILE_FORM, ratings: ['instrument', 'cfi'] as const };
    const onChange = renderFieldsets({ value: { ...value, ratings: [...value.ratings] } });

    await user.click(screen.getByLabelText('Instrument'));

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PROFILE_FORM, ratings: ['cfi'] });
  });

  it('reports a ticked volunteer interest through onChange', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.click(screen.getByLabelText('Newsletter'));

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PROFILE_FORM, vol_newsletter: true });
  });

  it('lists each DART with its airport identifier', () => {
    renderFieldsets();
    expect(screen.getByRole('option', { name: 'Palo Alto (PAO)' })).toBeInTheDocument();
  });

  it('says the DART list is loading while it is on its way', () => {
    renderFieldsets({ darts: [], dartsLoading: true });
    expect(screen.getByRole('option', { name: 'Loading DARTs…' })).toBeInTheDocument();
  });

  it('offers no DART as a choice once the list has arrived', () => {
    renderFieldsets();
    expect(screen.getByRole('option', { name: 'Not decided yet' })).toBeInTheDocument();
  });

  it('renders an error beside the field it belongs to', () => {
    renderFieldsets({ errors: { postal_code: 'Use a ZIP code like 95035 or 95035-1234.' } });

    const zip = screen.getByLabelText('ZIP code');
    expect(zip).toHaveAttribute('aria-invalid', 'true');
    expect(zip).toHaveAccessibleDescription('Use a ZIP code like 95035 or 95035-1234.');
  });

  it('leaves the other fields untouched by an error', () => {
    renderFieldsets({ errors: { postal_code: 'Use a ZIP code like 95035 or 95035-1234.' } });
    expect(screen.getByLabelText('City')).not.toHaveAttribute('aria-invalid');
  });

  it('marks the fields a member must fill in when markRequired is set', () => {
    renderFieldsets({ markRequired: true });
    expect(screen.getByLabelText('Phone*')).toBeInTheDocument();
  });

  it('leaves the required markers off by default', () => {
    renderFieldsets();
    expect(screen.getByLabelText('Phone')).toBeInTheDocument();
  });

  it('marks the certificate number once a certificate is chosen', () => {
    renderFieldsets({
      markRequired: true,
      value: { ...EMPTY_PROFILE_FORM, pilot_certificate_type: 'private' },
    });
    expect(screen.getByLabelText('Certificate number*')).toBeInTheDocument();
  });

  it('leaves the certificate number unmarked while the member is not a pilot', () => {
    renderFieldsets({ markRequired: true });
    expect(screen.getByLabelText('Certificate number')).toBeInTheDocument();
  });

  it('marks the medical expiry once a medical class is chosen', () => {
    renderFieldsets({
      markRequired: true,
      value: { ...EMPTY_PROFILE_FORM, medical_type: 'third' },
    });
    expect(screen.getByLabelText('Medical expires*')).toBeInTheDocument();
  });
});
