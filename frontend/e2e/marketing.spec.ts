import {test, expect} from '@playwright/test';
import {signIn} from './support/session';

const ACCOUNT_DATA = [
  'fixture/repository-a',
  'fixture/repository-b',
  'draft_created',
  'Scan now',
  'Release packs',
  'Recent operations',
];

test.describe('marketing landing page (C1, C2)', () => {
  test('C1: renders with no session, one primary CTA, a Login with GitHub control, no account data', async ({page}) => {
    const response = await page.goto('/');
    expect(response?.status()).toBe(200);
    await expect(page).toHaveURL(/\/$/);

    // Product story copy is present.
    await expect(page.getByRole('heading', {level: 1})).toBeVisible();
    await expect(page.getByText(/governed release/i)).toBeVisible();

    // Exactly one primary CTA, plus a distinct "Login with GitHub" control.
    await expect(page.getByRole('link', {name: 'Open the console'})).toBeVisible();
    const githubLogin = page.getByRole('link', {name: 'Login with GitHub'});
    await expect(githubLogin).toBeVisible();

    // No release / operation / repository data from any account.
    const body = await page.textContent('body');
    for (const needle of ACCOUNT_DATA) {
      expect(body ?? '').not.toContain(needle);
    }
    await expect(page.getByRole('button', {name: 'Scan now'})).toHaveCount(0);

    // The login control reaches the OAuth flow.
    await githubLogin.click();
    await expect(page).toHaveURL(/\/(auth\/github|dashboard|login)/);
  });

  test('C2: an authenticated visitor still sees the marketing page with a Go to dashboard CTA', async ({page}) => {
    await signIn(page);
    const response = await page.goto('/');
    expect(response?.status()).toBe(200);
    await expect(page).toHaveURL(/\/$/);

    const cta = page.getByRole('link', {name: 'Go to dashboard'});
    await expect(cta).toBeVisible();
    await expect(page.getByRole('link', {name: 'Login with GitHub'})).toHaveCount(0);

    await cta.click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});
