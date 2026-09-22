/** Shared plumbing for the end-to-end specs. */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** The keys `seed_demo` gives its named demo accounts. */
export type DemoAccount =
  'member' | 'expired' | 'leader' | 'useradmin' | 'accountadmin' | 'webadmin' | 'sysadmin';

/** What `manage.py seed_facts` reports about the seeded database. */
export interface SeedFacts {
  /** The password every seeded demo account shares. */
  demoPassword: string;
  /** Demo key to the address the seed gives that account. */
  accounts: Record<DemoAccount, string>;
  /** Membership plan slug to its price in cents. */
  planPricesCents: Record<string, number>;
}

const FACTS_PATH = resolve(dirname(fileURLToPath(import.meta.url)), 'seed-facts.json');

function readSeedFacts(): SeedFacts {
  try {
    return JSON.parse(readFileSync(FACTS_PATH, 'utf8')) as SeedFacts;
  } catch (cause) {
    throw new Error(
      `${FACTS_PATH} is missing or unreadable. \`make e2e\` writes it with ` +
        '`manage.py seed_facts` right after it seeds the database; write it by hand with ' +
        'the same command when you are running Playwright against a server you started ' +
        'yourself.',
      { cause },
    );
  }
}

/**
 * What the seeded database holds, read once per worker process.
 *
 * Assert prices and addresses against this rather than a literal copied out of
 * `apps/*\/seed.py`, so a change to the seed fails the spec honestly instead of
 * leaving it asserting a stale value.
 */
export const SEED: SeedFacts = readSeedFacts();

/** Every demo account seeded by `seed_demo` shares this password. */
export const DEMO_PASSWORD: string = SEED.demoPassword;

export const DEMO: Record<DemoAccount, string> = SEED.accounts;

/** Format a price in cents the way the portal renders it, e.g. `$45.00`. */
export function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/** An address nobody else in this run will use. */
export function uniqueEmail(prefix: string): string {
  const stamp = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  return `${prefix}-${stamp}@example.test`;
}

/** Sign in through the portal's own login form and wait for it to take. */
export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto('/portal/login');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/portal\/login/);
}

/** Sign in to the Wagtail admin, which has its own login form. */
export async function signInToWagtail(page: Page, email: string): Promise<void> {
  await page.goto('/admin/login/');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/admin\/?$/);
}
