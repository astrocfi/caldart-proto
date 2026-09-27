/**
 * The FAA registry on the aircraft forms and the System screen.
 *
 * The seed imports the registry fixture in `backend/apps/aircraft/fixtures/faa`,
 * and `make e2e` points `FAA_REGISTRY_URL` at the same directory, so Run now
 * imports the fixture again rather than downloading the FAA's registry.
 * `seed_facts` names a registration the fixture holds and the register does not
 * (`registry.knownNNumber`) and what a Look up on it answers.
 *
 * A member adds that airplane from My aircraft: Look up fills its type, year, and
 * owner, and a misspelled `cesna 172` still finds the Cessna 172.  An account
 * administrator adds an aircraft type the FAA has never registered from the
 * register's New aircraft form.  The system administrator runs the import.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, SEED, signIn } from './helpers';

const REGISTRY = SEED.registry;

/** The status the System screen and the register read, as `GET /aircraft/registry` answers it. */
interface RegistryStatus {
  as_of: string | null;
  running: boolean;
  last: {
    started_at: string;
    finished_at: string | null;
    ok: boolean;
    types_written: number;
    registrations_written: number;
    types_folded: number;
  } | null;
}

/** What `GET /aircraft/registry` answers now, read through the signed-in session. */
async function registryStatus(page: Page): Promise<RegistryStatus> {
  const response = await page.request.get('/api/v1/aircraft/registry');
  return (await response.json()) as RegistryStatus;
}

/** The Aircraft type box, the only way to set an aircraft's type. */
function typeBox(page: Page): Locator {
  return page.getByRole('combobox', { name: /^Aircraft type/ });
}

/** Type `text` into the Aircraft type box, replacing what it held, and wait for the list. */
async function searchTypes(page: Page, text: string): Promise<Locator> {
  const box = typeBox(page);
  await box.fill('');
  await box.pressSequentially(text);
  const list = page.getByRole('listbox', { name: 'Aircraft types' });
  await expect(list).toBeVisible();
  return list;
}

/** A day as the screens print it, `YYYY/MM/DD`, in this machine's time zone. */
function screenDate(iso: string): string {
  const day = new Date(iso);
  const month = String(day.getMonth() + 1).padStart(2, '0');
  const date = String(day.getDate()).padStart(2, '0');
  return `${day.getFullYear()}/${month}/${date}`;
}

/** A registration nobody has used: never in the fixture, whose N-numbers never end in ZQ. */
function unusedNNumber(): string {
  return `N${1 + Math.floor(Math.random() * 9)}${Math.floor(Math.random() * 100)}ZQ`;
}

/**
 * A model no fixture type holds: `Zq` and five random letters, written as the register
 * prints a word of letters longer than three.  It carries no digits, because a query
 * holding digits also finds every type whose model contains them.
 */
function unusedModel(): string {
  const letters = Array.from({ length: 5 }, () =>
    String.fromCharCode(97 + Math.floor(Math.random() * 26)),
  );
  return `Zq${letters.join('')}`;
}

test('a member looks up a registration and picks a misspelled type', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/profile/aircraft');
  await page.getByRole('button', { name: 'Add a new aircraft' }).click();

  await page.getByRole('textbox', { name: /^N-number/ }).fill(REGISTRY.knownNNumber);
  await page.getByRole('button', { name: 'Look up' }).click();

  await expect(page.getByText(`From the FAA registry as of ${REGISTRY.asOf}`)).toBeVisible();
  await expect(typeBox(page)).toHaveValue(REGISTRY.knownType);
  await expect(page.getByRole('textbox', { name: 'Year', exact: true })).toHaveValue(
    String(REGISTRY.knownYear),
  );
  await expect(page.getByRole('textbox', { name: 'Owner', exact: true })).toHaveValue(
    REGISTRY.knownOwner,
  );

  const list = await searchTypes(page, 'cesna 172');
  const leading = list.getByRole('option').first();
  await expect(leading).toHaveText(/^Cessna 172 /);
  await leading.click();
  await expect(typeBox(page)).toHaveValue('Cessna 172');

  await page.getByRole('button', { name: 'Add aircraft' }).click();

  const row = page.getByRole('listitem').filter({ hasText: REGISTRY.knownNNumber });
  await expect(row.getByText('Cessna 172', { exact: true })).toBeVisible();
});

test('an account administrator adds a type the FAA has never registered', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/aircraft');
  await expect(page.getByText(`Registry as of ${REGISTRY.asOf}`)).toBeVisible();
  await page.getByRole('button', { name: 'New aircraft' }).click();

  const nNumber = unusedNNumber();
  await page.getByRole('textbox', { name: /^N-number/ }).fill(nNumber);
  await page.getByRole('button', { name: 'Look up' }).click();
  await expect(page.getByText('Not in the FAA registry')).toBeVisible();

  const model = unusedModel();
  await typeBox(page).pressSequentially(`quillfeather ${model}`);
  await expect(page.getByText('No aircraft type matches that.')).toBeVisible();
  await page.getByRole('button', { name: 'Add a type' }).click();

  const adding = page.getByRole('group', { name: 'Add a type' });
  await adding.getByRole('textbox', { name: /^Make/ }).fill('Quillfeather');
  await adding.getByRole('textbox', { name: /^Model/ }).fill(model);
  await adding.getByRole('button', { name: 'Add type' }).click();

  await expect(adding).toHaveCount(0);
  await expect(typeBox(page)).toHaveValue(`Quillfeather ${model}`);

  await page.getByRole('button', { name: 'Add aircraft' }).click();
  await expect(page).toHaveURL(/\/portal\/admin\/aircraft\/\d+$/);
  await expect(typeBox(page)).toHaveValue(`Quillfeather ${model}`);
});

test('the system administrator runs the FAA registry import', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('/portal/system');

  // The System screen's panels are cards, each a section headed by its title.
  const panel = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'FAA registry import' }) });
  const started = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/admin/system/registry-import') &&
      response.request().method() === 'POST',
  );
  await panel.getByRole('button', { name: 'Run now' }).click();
  const response = await started;
  expect(response.status()).toBe(202);
  const startedAt = ((await response.json()) as { started_at: string }).started_at;

  // The import runs in its own process, which starts Django and reads the whole
  // fixture, so wait longer than the default expect timeout for this press's run to end.
  await expect
    .poll(
      async () => {
        const { running, last } = await registryStatus(page);
        return last?.started_at === startedAt && !running ? last.ok : null;
      },
      { timeout: 40_000 },
    )
    .toBe(true);
  const { last } = await registryStatus(page);
  if (last?.finished_at == null) throw new Error('The import the press started never finished.');

  await expect(panel.getByRole('status')).toHaveText(
    `Imported ${last.types_written} types and ${last.registrations_written} registrations on ` +
      `${screenDate(last.finished_at)}.`,
  );
  await expect(panel.getByRole('button', { name: 'Run now' })).toBeEnabled();
});
