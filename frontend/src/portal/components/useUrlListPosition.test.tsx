import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { orderingFor, pageFrom, sortFor, useUrlListPosition } from './useUrlListPosition';

function renderPosition(route: string, defaultOrdering = 'name') {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>;
  }
  return renderHook(() => useUrlListPosition(defaultOrdering), { wrapper: Wrapper });
}

describe('orderingFor', () => {
  it('turns an ascending column into its bare field', () => {
    expect(orderingFor('n_number', 'asc')).toBe('n_number');
  });

  it('prefixes a descending column with a minus sign', () => {
    expect(orderingFor('insurance_expiration', 'desc')).toBe('-insurance_expiration');
  });
});

describe('sortFor', () => {
  it('reads a bare field as ascending', () => {
    expect(sortFor('make')).toEqual({ key: 'make', direction: 'asc' });
  });

  it('reads a signed field as descending', () => {
    expect(sortFor('-paid_at')).toEqual({ key: 'paid_at', direction: 'desc' });
  });
});

describe('pageFrom', () => {
  it.each([
    ['', 1],
    ['3', 3],
    ['0', 1],
    ['-1', 1],
    ['2.5', 1],
    ['two', 1],
  ])('reads %j as page %i', (value, page) => {
    expect(pageFrom(value)).toBe(page);
  });
});

describe('useUrlListPosition', () => {
  it('uses the default order while the address names none', () => {
    const { result } = renderPosition('/list', '-paid_at');
    expect(result.current.sort).toEqual({ key: 'paid_at', direction: 'desc' });
  });

  it('reads the order and page from the address', () => {
    const { result } = renderPosition('/list?ordering=make&page=3');
    expect([result.current.ordering, result.current.page]).toEqual(['make', 3]);
  });

  it('returns to the first page when the order changes', () => {
    const { result } = renderPosition('/list?page=3');
    act(() => result.current.setSort('make', 'desc'));
    expect([result.current.ordering, result.current.page]).toEqual(['-make', 1]);
  });
});
