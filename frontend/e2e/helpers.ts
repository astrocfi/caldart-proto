/** Shared plumbing for the end-to-end specs. */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** The keys `seed_demo` gives its named demo accounts. */
export type DemoAccount =
  | 'member'
  | 'expired'
  | 'leader'
  | 'useradmin'
  | 'treasurer'
  | 'accountadmin'
  | 'webadmin'
  | 'sysadmin';

/** Every key `DemoAccount` names, so the facts can be checked against the whole set. */
const DEMO_ACCOUNT_KEYS: readonly DemoAccount[] = [
  'member',
  'expired',
  'leader',
  'useradmin',
  'treasurer',
  'accountadmin',
  'webadmin',
  'sysadmin',
];

/** The slugs `seed_plans` gives its membership plans. */
export type PlanSlug = 'annual' | 'life';

/** Every slug `PlanSlug` names, so the facts can be checked against the whole set. */
const PLAN_SLUGS: readonly PlanSlug[] = ['annual', 'life'];

/** One seeded member the leader check reads a particular way. */
export interface LeaderSubject {
  name: string;
  /** An aircraft they list, or empty when they list none. */
  nNumber: string;
}

/** One seeded payment that was refunded, and the member it belongs to. */
export interface RefundedPayment {
  name: string;
  email: string;
  /** The receipt number the payment carries, e.g. `CALDART-000017`. */
  receiptNumber: string;
}

/** The life member the seed gives a contribution-only standing authority. */
export interface ContributionMandateMember {
  name: string;
  email: string;
}

/** What `manage.py seed_facts` reports about the seeded database. */
export interface SeedFacts {
  /** The password every seeded demo account shares. */
  demoPassword: string;
  /** Demo key to the address the seed gives that account. */
  accounts: Record<DemoAccount, string>;
  /** Membership plan slug to its price in cents. */
  planPricesCents: Record<PlanSlug, number>;
  /**
   * Three members the leader check reads differently.  They come from the seed
   * rather than being typed into a spec, which drifts the moment the demo data
   * is generated a little differently.
   */
  leaderCheck: Record<'insuredPilot' | 'lapsedInsurance' | 'expiredMember', LeaderSubject>;
  /** How many payments the seed recorded by hand, which the finance list filters to. */
  manualPaymentCount: number;
  /** A member whose payment came back in part, for the refund assertions. */
  refundedPayment: RefundedPayment;
  /** The life member whose standing authority charges a contribution alone. */
  contributionMandate: ContributionMandateMember;
}

const LEADER_SUBJECT_KEYS = ['insuredPilot', 'lapsedInsurance', 'expiredMember'] as const;

const FACTS_PATH = resolve(dirname(fileURLToPath(import.meta.url)), 'seed-facts.json');

const WRITTEN_BY =
  '`make e2e` writes it with `manage.py seed_facts` right after it seeds the database; ' +
  'write it by hand with the same command when you are running Playwright against a ' +
  'server you started yourself.';

/** Reject facts that do not describe the seed the specs assert against. */
function rejectFacts(detail: string): never {
  throw new Error(
    `${FACTS_PATH} does not describe the seeded database: ${detail}. ${WRITTEN_BY} ` +
      'If the seed renamed it on purpose, rename it in e2e/helpers.ts too.',
  );
}

/** Narrow one JSON value to an object, or reject the facts naming the field. */
function objectField(source: Record<string, unknown>, field: string): Record<string, unknown> {
  const value = source[field];
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    rejectFacts(`\`${field}\` is not an object`);
  }
  return value as Record<string, unknown>;
}

/**
 * Check the parsed facts against what the specs read from them.
 *
 * Every `DemoAccount` key must carry a non-empty address and every `PlanSlug` a
 * price that is a whole number of cents above zero, so a renamed seed key fails
 * here, by name, instead of surfacing as an `undefined` address at sign-in or a
 * `$0.00` total in a checkout assertion.
 */
function checkedSeedFacts(parsed: unknown): SeedFacts {
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    rejectFacts('it is not a JSON object');
  }
  const root = parsed as Record<string, unknown>;

  const demoPassword = root.demoPassword;
  if (typeof demoPassword !== 'string' || demoPassword.length === 0) {
    rejectFacts('`demoPassword` is not a non-empty string');
  }

  const rawAccounts = objectField(root, 'accounts');
  const accountEntries = DEMO_ACCOUNT_KEYS.map((key) => {
    const email = rawAccounts[key];
    if (typeof email !== 'string' || email.length === 0) {
      rejectFacts(`\`accounts.${key}\` is missing or is not an address`);
    }
    return [key, email] as const;
  });

  const rawPrices = objectField(root, 'planPricesCents');
  const priceEntries = PLAN_SLUGS.map((slug) => {
    const price = rawPrices[slug];
    if (typeof price !== 'number' || !Number.isInteger(price) || price <= 0) {
      rejectFacts(`\`planPricesCents.${slug}\` is not a whole number of cents above zero`);
    }
    return [slug, price] as const;
  });

  const rawLeader = objectField(root, 'leaderCheck');
  const leaderEntries = LEADER_SUBJECT_KEYS.map((key) => {
    const subject = rawLeader[key] as { name?: unknown; nNumber?: unknown } | undefined;
    if (typeof subject?.name !== 'string' || subject.name.length === 0) {
      rejectFacts(`\`leaderCheck.${key}.name\` is missing: no seeded member fits that case`);
    }
    const nNumber = typeof subject.nNumber === 'string' ? subject.nNumber : '';
    return [key, { name: subject.name, nNumber }] as const;
  });

  const manualPaymentCount = root.manualPaymentCount;
  if (typeof manualPaymentCount !== 'number' || manualPaymentCount <= 0) {
    rejectFacts('`manualPaymentCount` is not a count above zero: the seed recorded no checks');
  }

  const rawRefunded = objectField(root, 'refundedPayment');
  const refundedText = (field: keyof RefundedPayment): string => {
    const value = rawRefunded[field];
    if (typeof value !== 'string' || value.length === 0) {
      rejectFacts(`\`refundedPayment.${field}\` is missing: no seeded payment was refunded`);
    }
    return value;
  };
  const refundedPayment: RefundedPayment = {
    name: refundedText('name'),
    email: refundedText('email'),
    receiptNumber: refundedText('receiptNumber'),
  };

  const rawRenewal = objectField(root, 'autoRenewal');
  const rawContribution = objectField(rawRenewal, 'contributionMandate');
  const contributionText = (field: keyof ContributionMandateMember): string => {
    const value = rawContribution[field];
    if (typeof value !== 'string' || value.length === 0) {
      rejectFacts(
        `\`autoRenewal.contributionMandate.${field}\` is missing: ` +
          'no seeded life member contributes automatically',
      );
    }
    return value;
  };
  const contributionMandate: ContributionMandateMember = {
    name: contributionText('name'),
    email: contributionText('email'),
  };

  return {
    demoPassword,
    accounts: Object.fromEntries(accountEntries) as Record<DemoAccount, string>,
    planPricesCents: Object.fromEntries(priceEntries) as Record<PlanSlug, number>,
    leaderCheck: Object.fromEntries(leaderEntries) as SeedFacts['leaderCheck'],
    manualPaymentCount,
    refundedPayment,
    contributionMandate,
  };
}

function readSeedFacts(): SeedFacts {
  let text: string;
  try {
    text = readFileSync(FACTS_PATH, 'utf8');
  } catch (cause) {
    throw new Error(`${FACTS_PATH} is missing or unreadable. ${WRITTEN_BY}`, { cause });
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (cause) {
    throw new Error(`${FACTS_PATH} is not valid JSON. ${WRITTEN_BY}`, { cause });
  }

  return checkedSeedFacts(parsed);
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
