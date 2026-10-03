import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EmailFrame, withNewTabLinks } from './EmailFrame';

const EMAIL =
  '<!doctype html><html lang="en"><head><meta charset="utf-8" /></head><body><a href="https://caldart.org">Site</a></body></html>';

describe('EmailFrame', () => {
  it('allows popups that leave the sandbox, and nothing else', () => {
    render(<EmailFrame title="The email" html={EMAIL} />);
    expect(screen.getByTitle('The email')).toHaveAttribute(
      'sandbox',
      'allow-popups allow-popups-to-escape-sandbox',
    );
  });

  it('carries only its class, its title, the sandbox, and the email', () => {
    render(<EmailFrame title="The email" html={EMAIL} />);
    expect(screen.getByTitle('The email').getAttributeNames().sort()).toEqual([
      'class',
      'sandbox',
      'srcdoc',
      'title',
    ]);
  });

  it("opens the email's links in a new tab", () => {
    render(<EmailFrame title="The email" html={EMAIL} />);
    expect(screen.getByTitle('The email').getAttribute('srcdoc')).toBe(
      '<!doctype html><html lang="en"><head><base target="_blank" rel="noopener"><meta charset="utf-8" /></head><body><a href="https://caldart.org">Site</a></body></html>',
    );
  });
});

describe('withNewTabLinks', () => {
  it('puts the base first in an email with no head', () => {
    expect(withNewTabLinks('<p>Hi</p>')).toBe('<base target="_blank" rel="noopener"><p>Hi</p>');
  });

  it('reads a head that carries attributes', () => {
    expect(withNewTabLinks('<HEAD lang="en"><title>x</title></HEAD>')).toBe(
      '<HEAD lang="en"><base target="_blank" rel="noopener"><title>x</title></HEAD>',
    );
  });
});
