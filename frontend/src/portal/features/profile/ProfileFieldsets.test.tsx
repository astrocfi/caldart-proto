import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { AddressSuggestion } from '@/portal/api/types';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { ProfileFieldsets } from './ProfileFieldsets';
import type { ProfileFieldsetsProps } from './ProfileFieldsets';
import { TEST_DARTS } from '@test/fixtures/profile';
import { EMPTY_PROFILE_FORM } from './form';
import type { ProfileFormValues } from './form';
import { ALL_VERIFIED, API, NONE_VERIFIED, NOT_VERIFIED } from '@test/handlers';

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
  'Photo ID',
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
  'Ground support',
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

  it('upper-cases a home airport as it is typed', async () => {
    const user = userEvent.setup();
    const onChange = renderFieldsets();

    await user.type(screen.getByLabelText('Home airport'), 'p');

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        home_airport_identifier: 'P',
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

  it('asks for the home airport without its leading K', () => {
    renderFieldsets();
    expect(screen.getByLabelText('Home airport')).toHaveAccessibleDescription(
      'Three characters, omit the leading K',
    );
  });

  it('calls the DART field a primary DART', () => {
    renderFieldsets();
    expect(screen.getByLabelText('DART')).toHaveAccessibleDescription('Your primary DART');
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

  it('offers the kinds of photo ID, and nothing else about the document', () => {
    renderFieldsets();
    const select = screen.getByLabelText('Photo ID');
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual([
      'Not provided',
      "Driver's license",
      'Passport',
      'State ID card',
      'Military ID',
      'Other',
    ]);
  });

  it('hands a picked photo ID back through onChange', async () => {
    const user = userEvent.setup();
    const handleChange = renderFieldsets();
    await user.selectOptions(screen.getByLabelText('Photo ID'), 'state_id');
    expect(handleChange).toHaveBeenLastCalledWith({
      ...EMPTY_PROFILE_FORM,
      photo_id_type: 'state_id',
    });
  });

  it('shows no verification mark unless the caller passes the verified state', () => {
    renderFieldsets();
    expect(screen.queryByText(/verified/i)).not.toBeInTheDocument();
  });

  it('marks each verified item in the member’s own wording', () => {
    renderFieldsets({
      verification: { ...ALL_VERIFIED, medical: NOT_VERIFIED },
    });
    expect(screen.getByLabelText('Medical')).toHaveAccessibleDescription('Not yet verified');
    expect(screen.getByLabelText('Photo ID')).toHaveAccessibleDescription(
      'Verified by Dana Leader on 2026/05/01',
    );
  });

  it('says who checks the items once, under the pilot certificate', () => {
    renderFieldsets({ verification: NONE_VERIFIED });
    expect(
      screen.getAllByText('A DART leader or verifier checks these against the documents.'),
    ).toHaveLength(1);
    expect(screen.getByLabelText('Pilot certificate')).toHaveAccessibleDescription(
      'Not yet verified A DART leader or verifier checks these against the documents.',
    );
  });
});

const AMPHITHEATRE: AddressSuggestion = {
  label: '1600 Amphitheatre Parkway, Mountain View, CA 94043',
  address_line1: '1600 Amphitheatre Parkway',
  city: 'Mountain View',
  state: 'CA',
  postal_code: '94043',
  county: 'Santa Clara',
};

const LAS_VEGAS: AddressSuggestion = {
  label: '1600 Amphitheater Drive, Las Vegas, NV 89109',
  address_line1: '1600 Amphitheater Drive',
  city: 'Las Vegas',
  state: 'NV',
  postal_code: '89109',
  county: '',
};

/** Answer `GET /addresses/suggest` with `suggestions`, recording each `q` it is sent. */
function suggestAddresses(suggestions: AddressSuggestion[]): string[] {
  const queries: string[] = [];
  server.use(
    http.get(`${API}/addresses/suggest`, ({ request }) => {
      queries.push(new URL(request.url).searchParams.get('q') ?? '');
      return HttpResponse.json(suggestions);
    }),
  );
  return queries;
}

/** The fieldsets holding their own value, as a form does, reporting every change. */
function StatefulFieldsets({
  initial,
  onChange: handleReport,
}: {
  initial: ProfileFormValues;
  onChange: (next: ProfileFormValues) => void;
}): JSX.Element {
  const [value, setValue] = useState(initial);
  const handleChange = (next: ProfileFormValues): void => {
    setValue(next);
    handleReport(next);
  };
  return <ProfileFieldsets value={value} onChange={handleChange} darts={TEST_DARTS} />;
}

function renderStateful(initial: ProfileFormValues = EMPTY_PROFILE_FORM) {
  const handleChange = vi.fn<(next: ProfileFormValues) => void>();
  renderWithProviders(<StatefulFieldsets initial={initial} onChange={handleChange} />);
  return handleChange;
}

describe('<ProfileFieldsets/> address suggestions', () => {
  it('offers the matching addresses under the Address box', async () => {
    suggestAddresses([AMPHITHEATRE, LAS_VEGAS]);
    const user = userEvent.setup();
    renderStateful();

    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');

    const list = await screen.findByRole('listbox', { name: 'Suggested addresses' });
    expect(
      within(list)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual([AMPHITHEATRE.label, LAS_VEGAS.label]);
  });

  it('asks the server with the street line as typed', async () => {
    const queries = suggestAddresses([AMPHITHEATRE]);
    const user = userEvent.setup();
    renderStateful();

    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');
    await screen.findByRole('listbox');

    expect(queries).toEqual(['1600 Amph']);
  });

  it('fills the street, city, state, ZIP code, and county at a pick', async () => {
    suggestAddresses([AMPHITHEATRE]);
    const user = userEvent.setup();
    const onChange = renderStateful({ ...EMPTY_PROFILE_FORM, address_line2: 'Building 40' });

    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');
    await user.click(await screen.findByRole('option', { name: AMPHITHEATRE.label }));

    expect(onChange).toHaveBeenLastCalledWith({
      ...EMPTY_PROFILE_FORM,
      address_line1: '1600 Amphitheatre Parkway',
      address_line2: 'Building 40',
      city: 'Mountain View',
      state: 'CA',
      postal_code: '94043',
      county: 'Santa Clara',
    });
  });

  it('clears the county when the picked address is outside California', async () => {
    suggestAddresses([LAS_VEGAS]);
    const user = userEvent.setup();
    const onChange = renderStateful({ ...EMPTY_PROFILE_FORM, county: 'Napa' });

    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');
    await user.click(await screen.findByRole('option', { name: LAS_VEGAS.label }));

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ state: 'NV', county: '' }) as Partial<ProfileFormValues>,
    );
  });

  it('keeps the state already chosen when the pick names none the form knows', async () => {
    suggestAddresses([{ ...AMPHITHEATRE, state: '', county: '' }]);
    const user = userEvent.setup();
    const onChange = renderStateful({ ...EMPTY_PROFILE_FORM, state: 'OR' });

    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');
    await user.click(await screen.findByRole('option', { name: AMPHITHEATRE.label }));

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ state: 'OR' }) as Partial<ProfileFormValues>,
    );
  });

  it('leaves every field editable after a pick', async () => {
    suggestAddresses([AMPHITHEATRE]);
    const user = userEvent.setup();
    renderStateful();
    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');
    await user.click(await screen.findByRole('option', { name: AMPHITHEATRE.label }));

    await user.clear(screen.getByLabelText('City'));
    await user.type(screen.getByLabelText('City'), 'Palo Alto');

    expect(screen.getByLabelText('City')).toHaveValue('Palo Alto');
  });

  it('offers nothing while the server has no suggestions', async () => {
    const queries = suggestAddresses([]);
    const user = userEvent.setup();
    renderStateful();

    await user.type(screen.getByRole('combobox', { name: 'Address' }), '1600 Amph');
    await waitFor(() => expect(queries).toEqual(['1600 Amph']));

    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('keeps what was typed when the member picks nothing', async () => {
    suggestAddresses([AMPHITHEATRE]);
    const user = userEvent.setup();
    renderStateful();
    const address = screen.getByRole('combobox', { name: 'Address' });

    await user.type(address, '1600 Amph');
    await screen.findByRole('listbox');
    await user.keyboard('{Escape}');

    expect(address).toHaveValue('1600 Amph');
  });
});
