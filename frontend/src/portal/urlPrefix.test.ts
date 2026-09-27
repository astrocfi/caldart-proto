import { afterEach, describe, expect, it } from 'vitest';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';
import type * as urlPrefix from './urlPrefix';

/** Import the module afresh, so it reads whatever `<html>` carries now. */
async function loadUrlPrefix(): Promise<typeof urlPrefix> {
  return import('./urlPrefix');
}

describe('urlPrefix without data-url-prefix', () => {
  afterEach(clearUrlPrefix);

  it('reads the prefix as empty', async () => {
    clearUrlPrefix();
    const { URL_PREFIX } = await loadUrlPrefix();
    expect(URL_PREFIX).toBe('');
  });

  it('leaves a site path at the root of the host', async () => {
    clearUrlPrefix();
    const { sitePath } = await loadUrlPrefix();
    expect(sitePath('/docs/')).toBe('/docs/');
  });

  it('puts the API at /api/v1', async () => {
    clearUrlPrefix();
    const { API_BASE } = await loadUrlPrefix();
    expect(API_BASE).toBe('/api/v1');
  });

  it('leaves a path alone when there is no prefix to strip', async () => {
    clearUrlPrefix();
    const { stripUrlPrefix } = await loadUrlPrefix();
    expect(stripUrlPrefix('/about/')).toBe('/about/');
  });

  it('mounts the portal at /portal', async () => {
    clearUrlPrefix();
    const { PORTAL_BASENAME } = await loadUrlPrefix();
    expect(PORTAL_BASENAME).toBe('/portal');
  });
});

describe('urlPrefix under data-url-prefix', () => {
  afterEach(clearUrlPrefix);

  it('reads the prefix the page carries', async () => {
    stampUrlPrefix('/x');
    const { URL_PREFIX } = await loadUrlPrefix();
    expect(URL_PREFIX).toBe('/x');
  });

  it('puts the prefix in front of a site path', async () => {
    stampUrlPrefix('/caldart-proto');
    const { sitePath } = await loadUrlPrefix();
    expect(sitePath('/docs/')).toBe('/caldart-proto/docs/');
  });

  it('keeps the trailing slash of the site root', async () => {
    stampUrlPrefix('/caldart-proto');
    const { sitePath } = await loadUrlPrefix();
    expect(sitePath('/')).toBe('/caldart-proto/');
  });

  it('puts the API under the prefix', async () => {
    stampUrlPrefix('/x');
    const { API_BASE } = await loadUrlPrefix();
    expect(API_BASE).toBe('/x/api/v1');
  });

  it('mounts the portal under the prefix', async () => {
    stampUrlPrefix('/x');
    const { PORTAL_BASENAME } = await loadUrlPrefix();
    expect(PORTAL_BASENAME).toBe('/x/portal');
  });

  it.each<[string, string]>([
    ['/x/about/', '/about/'],
    ['/x/', '/'],
    ['/x', '/'],
    ['/xyz/about/', '/xyz/about/'],
    ['/about/', '/about/'],
    ['https://example.org/x/about/', 'https://example.org/x/about/'],
  ])('reads %s as %s once the prefix is taken off', async (path, expected) => {
    stampUrlPrefix('/x');
    const { stripUrlPrefix } = await loadUrlPrefix();
    expect(stripUrlPrefix(path)).toBe(expected);
  });
});
