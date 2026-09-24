import { act, renderHook } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useClickOutside } from './useClickOutside';

/** A panel attached to the document, with a child to click inside it. */
function mountPanel(): { panel: HTMLDivElement; inside: HTMLButtonElement } {
  const panel = document.createElement('div');
  const inside = document.createElement('button');
  panel.append(inside);
  document.body.append(panel);
  return { panel, inside };
}

/** Send a real `pointerdown` the hook's document listener will see. */
function pointerDownOn(target: Element): void {
  act(() => {
    target.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));
  });
}

/** Send a keydown the hook's document listener will see. */
function pressKey(key: string): void {
  act(() => {
    document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  });
}

afterEach(() => {
  document.body.replaceChildren();
});

describe('useClickOutside', () => {
  it('leaves a press inside the element alone', () => {
    const { panel, inside } = mountPanel();
    const ref = createRef<HTMLDivElement>();
    Object.assign(ref, { current: panel });
    const handleOutside = vi.fn();
    renderHook(() => useClickOutside(ref, handleOutside, true));

    pointerDownOn(inside);

    expect(handleOutside).not.toHaveBeenCalled();
  });

  it('reports a press anywhere outside the element', () => {
    const { panel } = mountPanel();
    const ref = createRef<HTMLDivElement>();
    Object.assign(ref, { current: panel });
    const handleOutside = vi.fn();
    renderHook(() => useClickOutside(ref, handleOutside, true));

    pointerDownOn(document.body);

    expect(handleOutside).toHaveBeenCalledOnce();
  });

  it('reports Escape however the focus lies', () => {
    const { panel } = mountPanel();
    const ref = createRef<HTMLDivElement>();
    Object.assign(ref, { current: panel });
    const handleOutside = vi.fn();
    renderHook(() => useClickOutside(ref, handleOutside, true));

    pressKey('Escape');

    expect(handleOutside).toHaveBeenCalledOnce();
  });

  it('leaves any other key alone', () => {
    const { panel } = mountPanel();
    const ref = createRef<HTMLDivElement>();
    Object.assign(ref, { current: panel });
    const handleOutside = vi.fn();
    renderHook(() => useClickOutside(ref, handleOutside, true));

    pressKey('Enter');

    expect(handleOutside).not.toHaveBeenCalled();
  });

  it('listens to nothing while it is inactive', () => {
    const { panel } = mountPanel();
    const ref = createRef<HTMLDivElement>();
    Object.assign(ref, { current: panel });
    const handleOutside = vi.fn();
    renderHook(() => useClickOutside(ref, handleOutside, false));

    pointerDownOn(document.body);
    pressKey('Escape');

    expect(handleOutside).not.toHaveBeenCalled();
  });

  it('stops listening once it is unmounted', () => {
    const { panel } = mountPanel();
    const ref = createRef<HTMLDivElement>();
    Object.assign(ref, { current: panel });
    const handleOutside = vi.fn();
    const { unmount } = renderHook(() => useClickOutside(ref, handleOutside, true));

    unmount();
    pointerDownOn(document.body);

    expect(handleOutside).not.toHaveBeenCalled();
  });
});
