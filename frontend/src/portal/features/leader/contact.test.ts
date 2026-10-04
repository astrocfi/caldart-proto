import { describe, expect, it } from 'vitest';

import { contactHref } from './contact';

describe('contactHref', () => {
  it.each([
    ['ops@example.org', 'mailto:ops@example.org'],
    [' ops@example.org ', 'mailto:ops@example.org'],
    ['(650) 555-0100', 'tel:6505550100'],
    ['+1 650 555 0100', 'tel:+16505550100'],
  ])('links %j as %s', (text, href) => {
    expect(contactHref(text)).toBe(href);
  });

  it.each([[''], ['Ask at the front desk'], ['555-01']])('links nothing for %j', (text) => {
    expect(contactHref(text)).toBeNull();
  });
});
