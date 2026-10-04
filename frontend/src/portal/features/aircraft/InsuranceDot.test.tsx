import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { InsuranceDot } from './InsuranceDot';

const TODAY = new Date(2026, 5, 15); // 15 June 2026, local time

describe('InsuranceDot in a column of dates', () => {
  it.each([
    [true, '2027-04-29', 'current', 'Insured to 04/29/2027'],
    [true, '2026-07-10', 'expiring', 'Expiring 07/10/2026'],
    [false, '2026-03-02', 'expired', 'Expired 03/02/2026'],
  ] as const)(
    'says the state in words beside the date (current %s, %s)',
    (current, date, tone, word) => {
      render(
        <InsuranceDot
          aircraft={{ insurance_is_current: current, insurance_expiration: date }}
          today={TODAY}
          withDate
        />,
      );
      expect(screen.getByText(word)).toHaveAttribute('data-tone', tone);
    },
  );

  it('says no insurance is on file when there is no date', () => {
    render(
      <InsuranceDot
        aircraft={{ insurance_is_current: false, insurance_expiration: null }}
        today={TODAY}
        withDate
      />,
    );
    expect(screen.getByText('No insurance on file')).toHaveAttribute('data-tone', 'none');
  });
});
