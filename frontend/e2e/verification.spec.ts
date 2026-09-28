/**
 * Verification from end to end, as the Flow C step in `docs/demo-walkthrough.rst`
 * runs it: a DART leader verifies a pilot's certificate, medical, and photo ID from
 * the member check, and the account administrator hears about it once; the leader
 * makes that pilot a verifier, who verifies an airplane's insurance from the
 * aircraft check; and the pilot's own edit to their medical drops that item back to
 * unverified, on their profile and on a leader's card alike.
 *
 * One test, because each step stands on the one before it: the pilot the leader
 * verifies is the verifier who checks the airplane and the member who edits the
 * medical.  It writes to the seeded pilot and to one airplane, so it runs at
 * desktop size only.  A second test has the account administrator verify another
 * airplane from its aircraft record.
 *
 * Isolation rests on nothing else in the suite reading `SEED.leaderCheck.unverifiedPilot`,
 * the airplanes this spec picks from the register (one with current cover, one
 * without), or the account administrator's mail count: another spec touching any of
 * those would race this one.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, SEED, emailCountTo, latestEmailTo, signIn } from './helpers';

/** One register row as `GET /api/v1/aircraft` answers, cut to what this spec reads. */
interface RegisterRow {
  id: number;
  n_number: string;
  is_active: boolean;
  insurance_is_current: boolean;
  insurance_verification: { verified: boolean };
}

/** The member check's card for `name`, addressed by the accessible name it carries. */
function memberCard(page: Page, name: string): Locator {
  return page.getByRole('region', { name: `Status for ${name}` });
}

/** Search the member check for `term` and open the result named `name`. */
async function lookUp(page: Page, term: string, name: string): Promise<Locator> {
  await page.goto('portal/leader');
  await page.getByRole('searchbox', { name: 'Name, email, phone, or N-number' }).fill(term);
  await page.getByRole('button', { name: new RegExp(name) }).click();
  const card = memberCard(page, name);
  await expect(card).toBeVisible();
  return card;
}

/** One row of a status card, the value beside the term `term`. */
function row(card: Locator, term: string): Locator {
  return card
    .getByRole('term')
    .filter({ hasText: new RegExp(`^${term}$`) })
    .locator('xpath=following-sibling::dd[1]');
}

/** The signed-in person's name as the portal shows it, which is how a stamp names them. */
async function signedInName(page: Page): Promise<string> {
  const me = (await (await page.request.get('api/v1/auth/me')).json()) as {
    first_name: string;
    last_name: string;
  };
  return `${me.first_name} ${me.last_name}`;
}

/**
 * A registration whose insurance is current, whose airplane is in service, and whose
 * insurance nobody has verified, read from the register as the signed-in member.
 */
async function unverifiedAirplane(page: Page): Promise<string> {
  const response = await page.request.get('api/v1/aircraft?insurance=current&page_size=200');
  expect(response.status()).toBe(200);
  const { results } = (await response.json()) as { results: RegisterRow[] };
  const airplane = results.find(
    (each) => each.is_active && each.insurance_is_current && !each.insurance_verification.verified,
  );
  if (airplane === undefined) {
    throw new Error('The register holds no in-service airplane with unverified current cover.');
  }
  return airplane.n_number;
}

/**
 * An in-service airplane whose insurance is not current and nobody has verified, read
 * from the register as the signed-in account.  Lapsed cover keeps it apart from the
 * airplane `unverifiedAirplane` picks.
 */
async function unverifiedLapsedAirplane(page: Page): Promise<RegisterRow> {
  const response = await page.request.get('api/v1/aircraft?page_size=200');
  expect(response.status()).toBe(200);
  const { results } = (await response.json()) as { results: RegisterRow[] };
  const airplane = results.find(
    (each) => each.is_active && !each.insurance_is_current && !each.insurance_verification.verified,
  );
  if (airplane === undefined) {
    throw new Error('The register holds no in-service airplane with unverified lapsed cover.');
  }
  return airplane;
}

/** A date one day after `iso` (`YYYY-MM-DD`), in the same form. */
function dayAfter(iso: string): string {
  const next = new Date(`${iso}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return next.toISOString().slice(0, 10);
}

/** Sign out by dropping the session, then sign in as `email`. */
async function switchTo(page: Page, email: string): Promise<void> {
  await page.context().clearCookies();
  await signIn(page, email);
}

test('a leader verifies a pilot, who verifies an airplane and then edits a medical', async ({
  page,
}) => {
  const { name } = SEED.leaderCheck.unverifiedPilot;

  // The member check: nothing verified is a NO-GO naming each item.
  await signIn(page, DEMO.leader);
  const leaderName = await signedInName(page);
  const card = await lookUp(page, name, name);
  const verdict = card.getByRole('status');
  await expect(verdict).toContainText('NO-GO');
  await expect(verdict).toContainText('Medical not verified');
  await expect(verdict).toContainText('Certificate not verified');
  await expect(verdict).toContainText('Photo ID not verified');
  await expect(row(card, 'Photo ID')).toContainText('Not verified');
  const pilotEmail = (await card.getByRole('link', { name: /@/ }).innerText()).trim();

  // One save verifies all three, and the account administrator hears about it once.
  const mailBefore = emailCountTo(DEMO.accountadmin);
  await card.getByRole('button', { name: 'Verify' }).click();
  const panel = card.getByRole('group', { name: 'Checked against the documents' });
  await panel.getByRole('checkbox', { name: 'Pilot certificate verified' }).check();
  await panel.getByRole('checkbox', { name: 'Medical verified' }).check();
  await panel.getByRole('checkbox', { name: 'Photo ID verified' }).check();
  await card.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Verification saved')).toBeVisible();

  await expect(verdict).toContainText('GO');
  await expect(verdict).not.toContainText('NO-GO');
  await expect(verdict).toContainText('Membership and medical are current and verified');
  for (const term of ['Medical', 'Certificate', 'Photo ID']) {
    await expect(row(card, term)).toContainText(`Verified by ${leaderName} on`);
  }

  expect(emailCountTo(DEMO.accountadmin)).toBe(mailBefore + 1);
  const email = await latestEmailTo(DEMO.accountadmin);
  expect(email).toContain(
    `${leaderName} verified ${name}'s pilot certificate, medical, and photo ID`,
  );
  expect(email).toContain('Verified: Pilot certificate, Medical, Photo ID');
  expect(email).toContain('Cleared: None');

  // The leader makes the pilot a verifier from the same card.
  await card.getByRole('button', { name: 'Make a verifier' }).click();
  await expect(page.getByText(`${name} is a verifier.`)).toBeVisible();
  await expect(card.getByRole('button', { name: 'Remove as verifier' })).toBeVisible();
  await expect(card).toContainText('· Verifier');

  // The pilot, now a verifier, checks an airplane's insurance from the aircraft check.
  await switchTo(page, pilotEmail);
  const nNumber = await unverifiedAirplane(page);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Aircraft check' })
    .click();
  await page.getByRole('searchbox', { name: 'Search by N-number' }).fill(nNumber);
  const result = page.getByRole('button', { name: new RegExp(nNumber) });
  await expect(result).toContainText('Not verified');
  await result.click();

  const aircraftCard = page.getByRole('region', { name: `Insurance for ${nNumber}` });
  const aircraftVerdict = aircraftCard.getByRole('status');
  await expect(aircraftVerdict).toContainText('NOT VERIFIED');
  await expect(aircraftVerdict).toContainText('Coverage is current but not verified');
  await aircraftCard.getByRole('button', { name: 'Verify' }).click();
  await aircraftCard.getByRole('checkbox', { name: 'Insurance verified' }).check();
  await aircraftCard.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Verification saved')).toBeVisible();
  await expect(aircraftVerdict).toContainText('INSURED');
  await expect(aircraftVerdict).not.toContainText('NOT');
  await expect(row(aircraftCard, 'Insurance')).toContainText(`Verified by ${name} on`);

  // The pilot's own change to the medical drops that item, and that item alone.
  await switchTo(page, pilotEmail);
  await page.goto('portal/profile');
  const expires = page.getByLabel('Medical expires');
  const current = await expires.inputValue();
  expect(current).not.toBe('');
  await expires.fill(dayAfter(current));
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Profile saved.')).toBeVisible();
  // The medical's mark sits under the expiration date, the field a verifier checks.
  await expect(expires).toHaveAccessibleDescription(/Not yet verified/);
  await expect(
    page.getByRole('combobox', { name: 'Pilot certificate', exact: true }),
  ).toHaveAccessibleDescription(new RegExp(`Verified by ${leaderName} on`));

  // A leader's card reads the same: the medical needs checking again.
  await switchTo(page, DEMO.leader);
  const again = await lookUp(page, pilotEmail, name);
  await expect(again.getByRole('status')).toContainText('NO-GO');
  await expect(again.getByRole('status')).toContainText('Medical not verified');
  await expect(again.getByRole('status')).not.toContainText('Certificate not verified');
  await expect(again.getByRole('status')).not.toContainText('Photo ID not verified');
  await expect(row(again, 'Medical')).toContainText('Not verified');
});

test('an account administrator verifies an airplane from its aircraft record', async ({
  page,
}) => {
  await signIn(page, DEMO.accountadmin);
  const adminName = await signedInName(page);
  const airplane = await unverifiedLapsedAirplane(page);
  await page.goto(`portal/admin/aircraft/${airplane.id}`);

  const card = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Verification', exact: true }) });
  await expect(card).toContainText('Not verified');
  await card.getByRole('button', { name: 'Verify' }).click();
  await page.getByRole('checkbox', { name: 'Insurance verified' }).check();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByText('Verification saved')).toBeVisible();

  await expect(card).toContainText(`Verified by ${adminName} on`);
});
