import {test, expect} from '@playwright/test';
import {signIn} from './support/session';

const ACCOUNT_DATA = ['fixture/repository-a', 'fixture/repository-b', 'draft_created', 'Scan now', 'Recent operations'];

async function expectSharedChrome(page: import('@playwright/test').Page) {
  await expect(page.locator('main')).toHaveCount(1);
  for (const [name, href] of [['Product', '/'], ['About', '/about'], ['Contact', '/contact'], ['Sign in', '/login']]) {
    await expect(page.getByRole('navigation', {name: 'Primary navigation'}).getByRole('link', {name})).toHaveAttribute('href', href);
  }
  await expect(page.getByRole('navigation', {name: 'Footer navigation'})).toBeVisible();
}

test.describe('public marketing website', () => {
  test('landing page presents the governed workflow without account data', async ({page}) => {
    const response = await page.goto('/');
    expect(response?.status()).toBe(200);
    await expect(page).toHaveURL(/\/$/);
    await expectSharedChrome(page);
    await expect(page.getByRole('heading', {level: 1, name: /release with proof/i})).toBeVisible();
    await expect(page.getByRole('link', {name: 'Open the console'}).first()).toHaveAttribute('href', '/login');
    await expect(page.getByRole('link', {name: 'Why we built it'})).toHaveAttribute('href', '/about');

    const stages = await page.locator('.marketing-stages h3').allTextContents();
    expect(stages).toEqual(['Scan', 'Draft', 'Review', 'Publish', 'Rollback']);
    const headings = await page.locator('main h2').allTextContents();
    expect(headings.join(' ')).toMatch(/Automation prepares/);
    expect(headings.join(' ')).toMatch(/clear route to release/);
    expect(headings.join(' ')).toMatch(/Confidence you can inspect/);
    expect(headings.join(' ')).toMatch(/Product-building discipline/);

    const body = await page.textContent('body');
    for (const needle of ACCOUNT_DATA) expect(body ?? '').not.toContain(needle);
  });

  test('authenticated visitors remain on the public product page', async ({page}) => {
    await signIn(page);
    const response = await page.goto('/');
    expect(response?.status()).toBe(200);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('heading', {name: /release with proof/i})).toBeVisible();
  });

  test('about states its origin and governance purpose', async ({page}) => {
    expect((await page.goto('/about'))?.status()).toBe(200);
    await expectSharedChrome(page);
    await expect(page.getByText(/Release Manager is built by Shipyard/i)).toBeVisible();
    await expect(page.getByText(/Shipyard is Herald's product-building platform/i)).toBeVisible();
    await expect(page.getByText(/reviewable delivery/i)).toBeVisible();
  });

  test('contact is an internal coming-soon page without a form', async ({page}) => {
    expect((await page.goto('/contact'))?.status()).toBe(200);
    await expectSharedChrome(page);
    await expect(page).toHaveURL(/\/contact$/);
    await expect(page.getByText('Coming soon', {exact: true})).toBeVisible();
    await expect(page.getByRole('link', {name: 'Back to the product'})).toHaveAttribute('href', '/');
    await expect(page.locator('form')).toHaveCount(0);
    await expect(page.locator('a[href^="mailto:"], a[href^="http"]')).toHaveCount(0);
  });

  test('navigation is keyboard reachable and narrow layouts do not overflow', async ({page}) => {
    await page.setViewportSize({width: 360, height: 740});
    await page.goto('/');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', {name: 'Release Manager home'})).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('navigation', {name: 'Primary navigation'}).getByRole('link', {name: 'Product'})).toBeFocused();
    const sizes = await page.evaluate(() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth}));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.client);
    await expect(page.getByRole('heading', {name: /release with proof/i})).toBeVisible();
  });
});
