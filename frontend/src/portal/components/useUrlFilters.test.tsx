import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { useUrlFilters } from './useUrlFilters';

const KEYS = ['search', 'status', 'dart'] as const;

/** Mount the hook at `route`, alongside the location it writes to. */
function renderFilters(route: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>;
  }
  return renderHook(
    () => {
      const [values, setValues] = useUrlFilters(KEYS);
      return { values, setValues, location: useLocation() };
    },
    { wrapper: Wrapper },
  );
}

describe('useUrlFilters', () => {
  it('reads each key from the query string, an absent one as empty', () => {
    const { result } = renderFilters('/admin/members?search=dana&dart=4');

    expect(result.current.values).toEqual({ search: 'dana', status: '', dart: '4' });
  });

  it('reads nothing but the keys it was given', () => {
    const { result } = renderFilters('/admin/members?tab=history&page=3');

    expect(Object.keys(result.current.values)).toEqual(['search', 'status', 'dart']);
  });

  it('writes the values that are set and leaves the empty ones out', () => {
    const { result } = renderFilters('/admin/members?search=dana');

    act(() => result.current.setValues({ search: '', status: 'current', dart: '' }));

    expect(result.current.location.search).toBe('?status=current');
  });

  it('returns to page one when the filters change', () => {
    const { result } = renderFilters('/admin/members?page=3');

    act(() => result.current.setValues({ status: 'expired' }));

    expect(result.current.location.search).toBe('?status=expired');
  });

  it('keeps a parameter that is not one of its filters', () => {
    const { result } = renderFilters('/admin/members?ordering=-expires_on');

    act(() => result.current.setValues({ dart: '2' }));

    expect(result.current.location.search).toBe('?ordering=-expires_on&dart=2');
  });

  it('ignores a value whose key is not one of its filters', () => {
    const { result } = renderFilters('/admin/members');

    act(() => result.current.setValues({ dart: '2', page: '5' }));

    expect(result.current.location.search).toBe('?dart=2');
  });

  it('hands back the same values object while the URL stands still', () => {
    const { result, rerender } = renderFilters('/admin/members?search=dana');
    const first = result.current.values;

    rerender();

    expect(result.current.values).toBe(first);
  });
});
