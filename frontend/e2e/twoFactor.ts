/**
 * Two-factor sign-in for the end-to-end specs.
 *
 * Every demo staff account must use a second factor, and none has one when the run
 * seeds the database.  The first sign-in to such an account sets one up through the
 * portal's own screen, reads the key the screen offers for typing in by hand, and keeps
 * it in `frontend/e2e/.two-factor.json` (emptied at the start of each `make e2e`); every
 * later sign-in computes the code from it with the same RFC 6238 algorithm the server
 * uses.  Nothing about the second factor is fixed or switched off for the run.
 *
 * The server accepts each 30-second step's code once, and never a code older than the
 * last one accepted, so the step each account last used is kept in the same file and a code
 * is never offered twice; when the steps the server would accept are used up, the
 * helper waits for the clock.  A session that has passed the second factor is kept per
 * account for the life of the worker and reused while the server still honors it, so a
 * run that signs in as one account again and again rarely waits.
 */
import { createHmac } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect } from '@playwright/test';
import type { BrowserContext, Page } from '@playwright/test';

/** Where each account's key and last used step are kept between sign-ins. */
const STATE_PATH = resolve(dirname(fileURLToPath(import.meta.url)), '.two-factor.json');

/** RFC 6238 as the server applies it: 30-second steps, six digits, HMAC-SHA-1. */
const STEP_SECONDS = 30;
const DIGITS = 6;
/** Steps either side of the present one the server still accepts. */
const DRIFT_STEPS = 1;

const BASE32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

interface AccountState {
  secret: string;
  lastStep: number | null;
}

type State = Record<string, AccountState>;

/** The session cookies of each account that has passed the second factor. */
const sessions = new Map<string, Awaited<ReturnType<BrowserContext['cookies']>>>();

function readState(): State {
  if (!existsSync(STATE_PATH)) return {};
  return JSON.parse(readFileSync(STATE_PATH, 'utf8')) as State;
}

function writeState(state: State): void {
  writeFileSync(STATE_PATH, `${JSON.stringify(state, null, 2)}\n`);
}

function base32Decode(text: string): Buffer {
  const clean = text.replace(/[\s=]/g, '').toUpperCase();
  let bits = '';
  for (const char of clean) {
    const value = BASE32.indexOf(char);
    if (value < 0) throw new Error(`Not a base32 key: ${text}`);
    bits += value.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8)
    bytes.push(Number.parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** The code `secret` gives for time step `step`. */
export function totpAt(secret: string, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac('sha1', base32Decode(secret)).update(counter).digest();
  const offset = digest[digest.length - 1]! & 0x0f;
  const binary = digest.readUInt32BE(offset) & 0x7fffffff;
  return String(binary % 10 ** DIGITS).padStart(DIGITS, '0');
}

function currentStep(): number {
  return Math.floor(Date.now() / 1000 / STEP_SECONDS);
}

/**
 * A code for `email` the server has not seen: the present step's, or the next step's
 * when the present one is used, waiting for the clock when both are.
 */
async function nextCode(email: string): Promise<string> {
  const state = readState();
  const account = state[email];
  if (account === undefined) {
    throw new Error(
      `${email} already has two-factor sign-in, but ${STATE_PATH} doesn't hold a key for it. ` +
        'Reseed the database (make e2e does) so the run sets the account up itself.',
    );
  }
  for (;;) {
    const now = currentStep();
    // The present step's code, or the next one's: an older step's code could already be
    // outside the server's window by the time it arrives.
    const step = Math.max(now, (account.lastStep ?? -Infinity) + 1);
    if (step <= now + DRIFT_STEPS) {
      state[email] = { ...account, lastStep: step };
      writeState(state);
      return totpAt(account.secret, step);
    }
    // Every step the server would take is spent: wait until the next one opens.
    const opens = (step - DRIFT_STEPS) * STEP_SECONDS * 1000;
    await new Promise((done) => setTimeout(done, Math.max(250, opens - Date.now() + 250)));
  }
}

/** The heading the sign-in screen shows once the password step is over, if any. */
async function stepAfterPassword(page: Page): Promise<'verify' | 'enroll' | 'done'> {
  const handle = await page.waitForFunction(() => {
    const heading = document.querySelector('h1')?.textContent ?? '';
    if (heading === 'Two-factor sign-in') return 'verify';
    if (heading === 'Set up two-factor sign-in') return 'enroll';
    return window.location.pathname.endsWith('/portal/login') ? null : 'done';
  });
  return (await handle.jsonValue()) as 'verify' | 'enroll' | 'done';
}

/**
 * Finish a sign-in whose password was just given: give a code, or set two-factor
 * sign-in up and save the backup codes, as the screen asks.  Keeps the session for
 * `reuseSession` once the second factor has been passed.
 */
export async function finishSecondFactor(page: Page, email: string): Promise<void> {
  const step = await stepAfterPassword(page);
  if (step === 'done') return;
  if (step === 'enroll') {
    const key = (await page.locator('.enrollment__secret').textContent()) ?? '';
    const state = readState();
    state[email] = { secret: key.replace(/\s/g, ''), lastStep: null };
    writeState(state);
    await page.getByLabel(/^Code/).fill(await nextCode(email));
    await page.getByRole('button', { name: 'Confirm and continue' }).click();
    await page.getByRole('button', { name: 'I saved these' }).click();
  } else {
    await page.getByLabel(/^Code/).fill(await nextCode(email));
    await page.getByRole('button', { name: 'Sign in' }).click();
  }
  await expect(page.getByRole('heading', { level: 1, name: /two-factor sign-in$/i })).toHaveCount(
    0,
  );
  sessions.set(email, await page.context().cookies());
}

/**
 * Sign `page` in as `email` with the session kept from an earlier sign-in, when the
 * server still honors it; true when it did.  The page is not navigated.
 */
export async function reuseSession(page: Page, email: string): Promise<boolean> {
  const cookies = sessions.get(email);
  if (cookies === undefined) return false;
  await page.context().addCookies(cookies);
  const me = await page.request.get('api/v1/auth/me');
  const isSame =
    me.ok() && ((await me.json()) as { email: string }).email.toLowerCase() === email.toLowerCase();
  if (isSame) return true;
  sessions.delete(email);
  await page.context().clearCookies();
  return false;
}
