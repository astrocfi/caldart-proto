/**
 * The console guard: a test that writes to `console.error` or `console.warn`
 * fails, the frontend's answer to pytest's `filterwarnings = error`.
 *
 * `src/test/setup.ts` installs the guard before every test and checks it
 * afterwards.  A test that means to provoke a warning — React's own complaint
 * about an invalid prop, a library's deprecation notice — declares it with
 * `expectConsoleMessage(/…/)` before the code that writes it.
 *
 * The declaration is a two-way contract: an undeclared message fails the test,
 * and so does a declaration nothing matched, so a test whose subject is the
 * warning cannot quietly keep passing once the warning stops being written.
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
 * `console.error` or `console.warn` still fails the test, and so does this
 * declaration if no message matches it.
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
 * Throw when the test wrote a console message it did not declare, or declared
 * one it never wrote.
 *
 * The thrown error names every undeclared message, one per line, prefixed with
 * the method that wrote it, and every declared pattern nothing matched.  Either
 * way the guard's state is reset, so the next test starts from a clean slate.
 */
export function assertConsoleClean(): void {
  const patterns = expectedPatterns;
  const messages = captured;
  expectedPatterns = [];
  captured = [];

  const matched = new Set<RegExp>();
  const undeclared: CapturedMessage[] = [];
  for (const message of messages) {
    const matching = patterns.filter((pattern) => pattern.test(message.text));
    if (matching.length === 0) {
      undeclared.push(message);
      continue;
    }
    for (const pattern of matching) matched.add(pattern);
  }
  const unmatched = patterns.filter((pattern) => !matched.has(pattern));
  if (undeclared.length === 0 && unmatched.length === 0) return;

  const problems: string[] = [];
  if (undeclared.length > 0) {
    const lines = undeclared.map((message) => `  console.${message.method}: ${message.text}`);
    problems.push(
      `This test wrote ${undeclared.length} undeclared console message(s):\n${lines.join('\n')}\n` +
        'Fix the cause, or call expectConsoleMessage(/…/) from "@test/console" when the ' +
        'message is the behavior under test.',
    );
  }
  if (unmatched.length > 0) {
    const lines = unmatched.map((pattern) => `  ${pattern.toString()}`);
    problems.push(
      `This test declared ${unmatched.length} console message(s) nothing wrote:\n` +
        `${lines.join('\n')}\n` +
        'The message this test is about has stopped being written: assert on what the ' +
        'code does instead, or drop the expectConsoleMessage(/…/) declaration.',
    );
  }
  throw new Error(problems.join('\n\n'));
}
