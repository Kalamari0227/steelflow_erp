import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useReducedMotion } from './OperationsScene';

class MotionPreference extends EventTarget implements MediaQueryList {
  matches = false;
  readonly media = '(prefers-reduced-motion: reduce)';
  onchange: MediaQueryList['onchange'] = null;
  addListener(): void { throw new Error('Deprecated media listeners must not be used'); }
  removeListener(): void { throw new Error('Deprecated media listeners must not be used'); }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('scene reduced-motion preference', () => {
  it('observes preference changed after initial render but before subscription', () => {
    const query = new MotionPreference();
    let reads = 0;
    vi.stubGlobal('matchMedia', vi.fn(() => {
      reads += 1;
      if (reads === 2) query.matches = true;
      return query;
    }));
    const { result } = renderHook(() => useReducedMotion());
    expect(reads).toBe(2);
    expect(result.current).toBe(true);
  });

  it('follows later preference toggles and removes the exact subscription on unmount', () => {
    const query = new MotionPreference();
    vi.stubGlobal('matchMedia', vi.fn(() => query));
    const added = vi.spyOn(query, 'addEventListener');
    const removed = vi.spyOn(query, 'removeEventListener');
    const { result, unmount } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    act(() => { query.matches = true; query.dispatchEvent(new Event('change')); });
    expect(result.current).toBe(true);
    act(() => { query.matches = false; query.dispatchEvent(new Event('change')); });
    expect(result.current).toBe(false);
    const listener = added.mock.calls[0]?.[1];
    expect(listener).toBeTypeOf('function');
    unmount();
    expect(removed).toHaveBeenCalledWith('change', listener);
  });
});
