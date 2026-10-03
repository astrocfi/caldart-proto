import { describe, expect, it } from 'vitest';

import { EMAIL_IMAGE_WIDTH, emailImageSize, linkAddress } from './richText';

describe('linkAddress', () => {
  it.each([
    ['https://caldart.org/events', 'https://caldart.org/events'],
    ['http://caldart.org', 'http://caldart.org'],
    ['HTTPS://caldart.org', 'HTTPS://caldart.org'],
    ['mailto:ops@caldart.org', 'mailto:ops@caldart.org'],
    ['  https://caldart.org  ', 'https://caldart.org'],
    ['caldart.org/events', 'https://caldart.org/events'],
    ['www.caldart.org', 'https://www.caldart.org'],
    ['caldart.org:8080/x', 'https://caldart.org:8080/x'],
    ['ops@caldart.org', 'mailto:ops@caldart.org'],
  ])('reads %j as %j', (typed, expected) => {
    expect(linkAddress(typed)).toBe(expected);
  });

  it.each(['', '   ', 'javascript:alert(1)', 'data:text/html,x', 'ftp://x.org', 'two words'])(
    'refuses %j',
    (typed) => {
      expect(linkAddress(typed)).toBeNull();
    },
  );
});

describe('emailImageSize', () => {
  it('keeps an image no wider than an email at its own size', () => {
    expect(emailImageSize(EMAIL_IMAGE_WIDTH, 200)).toEqual({ width: 600, height: 200 });
  });

  it('scales a wider image to the email width, keeping its proportions', () => {
    expect(emailImageSize(1200, 601)).toEqual({ width: 600, height: 301 });
  });

  it('never makes an image less than one pixel high', () => {
    expect(emailImageSize(1200, 1)).toEqual({ width: 600, height: 1 });
  });
});
