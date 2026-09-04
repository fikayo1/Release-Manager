import {expect, Page} from '@playwright/test';

/**
 * Complete the deterministic OAuth flow so the browser context holds a valid
 * `release_manager_session` cookie and the backend has a connected user.
 * Idempotent: re-authorising the shared fixture backend is safe.
 */
export async function signIn(page: Page) {
  await page.goto('/login');
  if (!page.url().includes('/dashboard')) {
    await page.getByRole('link', {name: 'Login with GitHub'}).click();
  }
  await expect(page).toHaveURL(/\/dashboard$/);
}
