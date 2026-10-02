/** Shared plumbing for the end-to-end specs. */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** The keys `seed_demo` gives its named demo accounts. */
export type DemoAccount =
  | 'member'
  | 'expired'
  | 'friend'
  | 'leader'
  | 'verifier'
  | 'useradmin'
  | 'treasurer'
  | 'accountadmin'
  | 'management'
  | 'webadmin'
  | 'sysadmin';

/** Every key `DemoAccount` names, so the facts can be checked against the whole set. */
const DEMO_ACCOUNT_KEYS: readonly DemoAccount[] = [
  'member',
  'expired',
  'friend',
  'leader',
  'verifier',
  'useradmin',
  'treasurer',
  'accountadmin',
  'management',
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

/**
 * A registration the FAA registry fixture holds and the aircraft register does not,
 * and what picking it from the N-number box fills in.
 */
export interface RegistryFacts {
  /** The N-number, with its leading N, e.g. `N10131`. */
  knownNNumber: string;
  /** Its aircraft type as the screens print it: make, then model. */
  knownType: string;
  knownYear: number;
  /** The registrant's name, which picking the registration writes into the owner's name. */
  knownOwner: string;
  /** The day the newest successful import finished, as `MM/DD/YYYY`. */
  asOf: string;
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
   * Four members the leader check reads differently: an insured pilot verified on
   * every count, one whose airplane's insurance has lapsed, one whose membership
   * has, and a current pilot with a current medical whose certificate, medical, and
   * photo ID nobody has verified (`unverifiedPilot`).  They come from the seed
   * rather than being typed into a spec, which drifts the moment the demo data is
   * generated a little differently.
   */
  leaderCheck: Record<LeaderSubjectKey, LeaderSubject>;
  /** How many payments the seed recorded by hand, which the finance list filters to. */
  manualPaymentCount: number;
  /** A member whose payment came back in part, for the refund assertions. */
  refundedPayment: RefundedPayment;
  /** The life member whose standing authority charges a contribution alone. */
  contributionMandate: ContributionMandateMember;
  /** A registration for the N-number box on the aircraft forms, and the registry's date. */
  registry: RegistryFacts;
}

const LEADER_SUBJECT_KEYS = [
  'insuredPilot',
  'lapsedInsurance',
  'expiredMember',
  'unverifiedPilot',
] as const;

/** The keys `seed_facts` gives the members the leader check reads differently. */
type LeaderSubjectKey = (typeof LEADER_SUBJECT_KEYS)[number];

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

  const rawRegistry = objectField(root, 'registry');
  const registryText = (field: Exclude<keyof RegistryFacts, 'knownYear'>): string => {
    const value = rawRegistry[field];
    if (typeof value !== 'string' || value.length === 0) {
      rejectFacts(
        `\`registry.${field}\` is missing: the registry holds no registration to look up`,
      );
    }
    return value;
  };
  const knownYear = rawRegistry.knownYear;
  if (typeof knownYear !== 'number' || !Number.isInteger(knownYear)) {
    rejectFacts(
      '`registry.knownYear` is not a year: the registry holds no registration to look up',
    );
  }
  const registry: RegistryFacts = {
    knownNNumber: registryText('knownNNumber'),
    knownType: registryText('knownType'),
    knownYear,
    knownOwner: registryText('knownOwner'),
    asOf: registryText('asOf'),
  };

  return {
    demoPassword,
    accounts: Object.fromEntries(accountEntries) as Record<DemoAccount, string>,
    planPricesCents: Object.fromEntries(priceEntries) as Record<PlanSlug, number>,
    leaderCheck: Object.fromEntries(leaderEntries) as SeedFacts['leaderCheck'],
    manualPaymentCount,
    refundedPayment,
    contributionMandate,
    registry,
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

/** Write a `YYYY-MM-DD` day the way the portal renders it, e.g. `09/27/2026`. */
export function displayDate(iso: string): string {
  const [year, month, day] = iso.split('-');
  return `${month}/${day}/${year}`;
}

/** An address nobody else in this run will use. */
export function uniqueEmail(prefix: string): string {
  const stamp = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  return `${prefix}-${stamp}@example.test`;
}

/** Sign in through the portal's own login form and wait for it to take. */
export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto('portal/login');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/portal\/login/);
}

/** Sign in to the Wagtail admin, which has its own login form. */
export async function signInToWagtail(page: Page, email: string): Promise<void> {
  await page.goto('admin/login/');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/admin\/?$/);
}

/**
 * Where `make e2e` has Django write every message it sends: one file per message,
 * through the file mail backend.  The directory is emptied at the start of each run.
 */
const MAIL_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '.mail');

/** How long `latestEmailTo` waits for a message to arrive before giving up. */
const MAIL_WAIT_MS = 10_000;
const MAIL_POLL_MS = 200;

/**
 * Undo quoted-printable: join the soft line breaks, then turn every `=XX` back into
 * its byte.  The bodies are UTF-8, so the bytes are decoded as UTF-8 at the end.
 */
function decodeQuotedPrintable(text: string): string {
  const joined = text.replace(/=\r?\n/g, '');
  const bytes: number[] = [];
  for (let i = 0; i < joined.length; i += 1) {
    const hex = joined.slice(i + 1, i + 3);
    if (joined[i] === '=' && /^[0-9A-F]{2}$/.test(hex)) {
      bytes.push(Number.parseInt(hex, 16));
      i += 2;
    } else {
      bytes.push(joined.charCodeAt(i));
    }
  }
  return Buffer.from(bytes).toString('utf8');
}

interface MessageFile {
  path: string;
  name: string;
}

/** Every message file in the mail directory, newest first, none read yet. */
function sortedMessageFiles(): MessageFile[] {
  if (!existsSync(MAIL_DIR)) return [];
  return readdirSync(MAIL_DIR)
    .map((name) => ({ path: resolve(MAIL_DIR, name), name }))
    .map((file) => ({ ...file, mtime: statSync(file.path).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime || b.name.localeCompare(a.name));
}

/** True when message file `raw` is addressed to `address`. */
function isAddressedTo(raw: string, address: string): boolean {
  const header = `to: ${address}`.toLowerCase();
  return raw.split(/\r?\n/).some((line) => line.toLowerCase() === header);
}

/** Every message file addressed to `address`, decoded, newest first. */
function messagesTo(address: string): string[] {
  return sortedMessageFiles()
    .map((file) => readFileSync(file.path, 'utf8'))
    .filter((raw) => isAddressedTo(raw, address))
    .map(decodeQuotedPrintable);
}

/**
 * The newest message file addressed to `address`, decoded, or null when there is none.
 *
 * Reads files newest first and stops at the first match, rather than decoding every
 * message in the directory to find the one that matters.
 */
function newestMessageTo(address: string): string | null {
  for (const file of sortedMessageFiles()) {
    const raw = readFileSync(file.path, 'utf8');
    if (isAddressedTo(raw, address)) return decodeQuotedPrintable(raw);
  }
  return null;
}

/**
 * How many emails have been sent to `address` so far in this run.
 *
 * A message is written before the response to the request that sent it, so a
 * count read once that response has landed is final for that request: compare
 * one taken before with one taken after to prove a request sent nothing.
 */
export function emailCountTo(address: string): number {
  return messagesTo(address).length;
}

/**
 * The newest email sent to `address`, as text with its bodies decoded.
 *
 * Waits up to ten seconds for one to arrive, since the server writes it after the
 * request that caused it; throws naming the address when none does.
 */
export async function latestEmailTo(address: string): Promise<string> {
  const deadline = Date.now() + MAIL_WAIT_MS;
  for (;;) {
    const message = newestMessageTo(address);
    if (message !== null) return message;
    if (Date.now() > deadline) {
      throw new Error(`No email to ${address} in ${MAIL_DIR}. Is EMAIL_URL the file backend?`);
    }
    await new Promise((settle) => setTimeout(settle, MAIL_POLL_MS));
  }
}

/** The first `/portal/verify-email?token=` link in an email's text. */
export function verificationLink(text: string): string {
  const match = /https?:\/\/\S+?\/portal\/verify-email\?token=[^\s"<&]+/.exec(text);
  if (match === null) throw new Error(`No verification link in:\n${text}`);
  return match[0];
}

/**
 * Follow the newest verification link mailed to `email`, as its owner would, and
 * press `Continue` on the page it opens.  A signed-in joiner lands back in the join
 * wizard at the profile step.
 */
export async function followVerificationLink(page: Page, email: string): Promise<void> {
  await page.goto(verificationLink(await latestEmailTo(email)));
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await page.getByRole('link', { name: 'Continue' }).click();
}

/** The password every account a spec registers through the join wizard is given. */
export const JOINER_PASSWORD = 'a-long-demo-passphrase';

/** How a spec's fresh account joins: as a member, who pays, or as a friend, who does not. */
export interface JoinAs {
  as: 'member' | 'friend';
  /** The first name on the account; `Casey` when left out. */
  firstName?: string;
}

/**
 * Create an account at the join wizard's first step, which signs its owner in and
 * ends on the verify step, the only screen an unverified account may see.
 */
export async function registerAccount(
  page: Page,
  email: string,
  { as, firstName = 'Casey' }: JoinAs,
): Promise<void> {
  await page.goto('portal/join');
  if (as === 'friend') await page.getByRole('radio', { name: /Join as a friend/ }).check();
  await page.getByRole('textbox', { name: 'First name' }).fill(firstName);
  await page.getByRole('textbox', { name: 'Last name' }).fill('Okafor');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/portal\/join\/verify/);
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
}

/**
 * Fill the fields that make the profile complete on the join wizard's profile step,
 * and save them, which moves the wizard on to the pay step.
 */
export async function completeProfileStep(page: Page): Promise<void> {
  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('650-555-0190');
  await page.getByRole('combobox', { name: 'Address', exact: true }).fill('4 Hangar Row');
  await page.getByRole('textbox', { name: 'City', exact: true }).fill('Hollister');
  await page.getByRole('textbox', { name: 'ZIP code', exact: true }).fill('95023');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page).toHaveURL(/\/portal\/join\/pay/);
}

/**
 * Walk a fresh account at `email` through the whole join wizard, which is the whole
 * portal until it is done: register, follow the verification link, complete the
 * profile, then pay the annual dues with the mock provider (a member) or press
 * **Not now** (a friend).  Ends on the wizard's done step, with the rest of the
 * portal open.
 */
export async function completeOnboarding(page: Page, email: string, joinAs: JoinAs): Promise<void> {
  await registerAccount(page, email, joinAs);
  await followVerificationLink(page, email);
  await completeProfileStep(page);
  if (joinAs.as === 'member') {
    await page.getByRole('tab', { name: 'Test payment' }).click();
    await page.getByRole('button', { name: 'Succeed', exact: true }).click();
  } else {
    // Wait for the payment options, so the click lands on the loaded form's button.
    await expect(page.getByRole('radio', { name: /Participating/ })).toBeVisible();
    await page.getByRole('button', { name: 'Not now' }).click();
  }
  await expect(page).toHaveURL(/\/portal\/join\/done/);
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
}
