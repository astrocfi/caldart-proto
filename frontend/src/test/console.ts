/**
 * The console guard: a test that writes to `console.error` or `console.warn`
 * fails, the frontend's answer to pytest's `filterwarnings = error`.
 *
 * `src/test/setup.ts` installs the guard before every test and checks it
 * afterwards.  A test that means to provoke a warning — React's own complaint
 * about an invalid prop, a library's deprecation notice — declares it with
 * `expectConsoleMessage(/…/)` before the code that writes it.
 */
import { vi } from 'vitest';

/** The console methods a test may not write to without declaring the message. */
const GUARDED_METHODS = ['error', 'warn'] as const;

type GuardedMethod = (typeof GUARDED_METHODS)[number];

interface CapturedMessage {
  method: GuardedMethod;
  text: string;
}

let expectedPatterns: RegExp[] = [];
let captured: CapturedMessage[] = [];

/**
 * Declare that the test about to run writes a console message matching
 * `pattern`, so the guard lets that one message through.
 *
 * The declaration lasts for the current test only.  Every other message on
 * `console.error` or `console.warn` still fails the test.
 */
export function expectConsoleMessage(pattern: RegExp): void {
  expectedPatterns.push(pattern);
}

/** Replace the guarded console methods with capturing spies. */
export function installConsoleGuard(): void {
  expectedPatterns = [];
  captured = [];
  for (const method of GUARDED_METHODS) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      captured.push({ method, text: args.map((arg) => String(arg)).join(' ') });
    });
  }
}

/**
 * Throw when the test wrote a console message it did not declare.
 *
 * The thrown error names every undeclared message, one per line, prefixed with
 * the method that wrote it.
 */
export function assertConsoleClean(): void {
  const undeclared = captured.filter(
    (message) => !expectedPatterns.some((pattern) => pattern.test(message.text)),
  );
  expectedPatterns = [];
  captured = [];
  if (undeclared.length === 0) return;

  const lines = undeclared.map((message) => `  console.${message.method}: ${message.text}`);
  throw new Error(
    `This test wrote ${undeclared.length} undeclared console message(s):\n${lines.join('\n')}\n` +
      'Fix the cause, or call expectConsoleMessage(/…/) from "@test/console" when the ' +
      'message is the behavior under test.',
  );
}
