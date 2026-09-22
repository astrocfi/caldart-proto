/**
 * The console guard's own tests.
 *
 * Each case reinstalls the guard and calls `assertConsoleClean` itself, which
 * resets the guard's state, so `setup.ts`'s own check afterwards sees a clean
 * slate whatever this test did.
 */
import { describe, expect, it } from 'vitest';

import { assertConsoleClean, expectConsoleMessage, installConsoleGuard } from './console';

describe('assertConsoleClean', () => {
  it('passes when the test wrote nothing', () => {
    installConsoleGuard();

    expect(() => assertConsoleClean()).not.toThrow();
  });

  it('fails when the test wrote an undeclared message', () => {
    installConsoleGuard();
    console.error('boom: a prop went missing');

    expect(() => assertConsoleClean()).toThrow(/boom: a prop went missing/);
  });

  it('passes when the declared pattern matches the message written', () => {
    installConsoleGuard();
    expectConsoleMessage(/must be used inside/);
    console.warn('useToast must be used inside a <ToastProvider>');

    expect(() => assertConsoleClean()).not.toThrow();
  });

  it('fails when a declared message is never written', () => {
    installConsoleGuard();
    expectConsoleMessage(/must be used inside/);

    expect(() => assertConsoleClean()).toThrow(/declared 1 console message\(s\) nothing wrote/);
  });

  it('names the declaration nothing matched', () => {
    installConsoleGuard();
    expectConsoleMessage(/a warning that stopped/);

    expect(() => assertConsoleClean()).toThrow(/\/a warning that stopped\//);
  });

  it('leaves no declaration behind for the next test', () => {
    installConsoleGuard();
    expectConsoleMessage(/never written/);
    expect(() => assertConsoleClean()).toThrow();

    expect(() => assertConsoleClean()).not.toThrow();
  });
});
