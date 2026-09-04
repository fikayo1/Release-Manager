import {test, expect} from '@playwright/test';

const SECTIONS: [string, RegExp][] = [
  ['Home', /\/dashboard$/],
  ['Releases', /\/dashboard\/releases$/],
  ['Operations', /\/dashboard\/operations$/],
  ['Repos', /\/dashboard\/settings\/github$/],
  ['Schedule', /\/dashboard\/settings\/schedule$/],
];

test.describe('editorial sign-in and dashboard shell (C4, C5, C6)', () => {
  test('C4: /login renders with no session and completing OAuth lands on /dashboard', async ({page}) => {
    const response = await page.goto('/login');
    expect(response?.status()).toBe(200);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', {name: /sign in/i})).toBeVisible();

    const button = page.getByRole('link', {name: 'Login with GitHub'});
    await expect(button).toBeVisible();
    await button.click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', {name: 'Home'})).toBeVisible();
  });

  test('C5: a desktop viewport shows a left sidebar (no top nav) with working links and logo', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await page.goto('/login');
    await page.getByRole('link', {name: 'Login with GitHub'}).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    const sidebar = page.getByRole('navigation', {name: 'Dashboard sections'});
    await expect(sidebar).toBeVisible();
    await expect(page.getByRole('button', {name: 'Sign out'})).toBeVisible();
    // No separate top navigation landmark.
    await expect(page.getByRole('navigation', {name: /primary/i})).toHaveCount(0);
    // The toggle is not shown at desktop width.
    await expect(page.getByRole('button', {name: 'Menu'})).toBeHidden();

    for (const [label, urlRe] of SECTIONS) {
      await sidebar.getByRole('link', {name: label}).click();
      await expect(page).toHaveURL(urlRe);
      await expect(page.getByRole('navigation', {name: 'Dashboard sections'})
        .getByRole('link', {name: label})).toHaveAttribute('aria-current', 'page');
    }

    await page.getByRole('link', {name: /Release Manager/}).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test('C5: a narrow viewport collapses the sidebar to a working toggle', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await page.goto('/login');
    await page.getByRole('link', {name: 'Login with GitHub'}).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    // Ensure the client shell has hydrated before exercising the toggle.
    await expect(page.getByRole('heading', {name: 'Home'})).toBeVisible();

    await page.setViewportSize({width: 480, height: 900});
    const nav = page.getByRole('navigation', {name: 'Dashboard sections'});
    await expect(page.getByRole('button', {name: 'Menu'})).toBeVisible();
    await expect(nav).toBeHidden();
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', {name: 'Menu'}).click();
    await expect(page.getByRole('button', {name: 'Close menu'})).toBeVisible();
    await expect(nav).toBeVisible();

    await page.getByRole('button', {name: 'Close menu'}).click();
    await expect(nav).toBeHidden();
  });

  test('C6: a gold accent is applied to a primary action and the active nav item', async ({page}) => {
    await page.setViewportSize({width: 1280, height: 900});
    await page.goto('/login');
    await page.getByRole('link', {name: 'Login with GitHub'}).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    const scan = page.getByRole('button', {name: 'Scan now'});
    await expect(scan).toBeVisible();
    const scanBg = await scan.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(scanBg).toBe('rgb(201, 162, 39)');

    const active = page.getByRole('navigation', {name: 'Dashboard sections'})
      .getByRole('link', {name: 'Home'});
    const activeColor = await active.evaluate((el) => getComputedStyle(el).color);
    expect(activeColor).toBe('rgb(111, 82, 12)');
  });
});
