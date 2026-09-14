/** Shared plumbing for the end-to-end specs. */
import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** Every demo account seeded by `seed_demo` shares this password. */
export const DEMO_PASSWORD = 'caldart-demo';

export const DEMO = {
  member: 'member@example.org',
  expired: 'expired@example.org',
  leader: 'leader@example.org',
  userAdmin: 'useradmin@example.org',
  accountAdmin: 'accountadmin@example.org',
  webAdmin: 'webadmin@example.org',
  sysAdmin: 'sysadmin@example.org',
} as const;

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
