import {test, expect} from '@playwright/test';

const API = `http://127.0.0.1:${process.env.SHIPYARD_E2E_API_PORT ?? '18000'}`;

const DASHBOARD_ROUTES = [
  '/dashboard',
  '/dashboard/releases',
  '/dashboard/operations',
  '/dashboard/settings/github',
  '/dashboard/settings/schedule',
];

test.describe('dashboard auth gate (C3)', () => {
  test('every /dashboard route redirects an unauthenticated visitor to /login', async ({page}) => {
    for (const route of DASHBOARD_ROUTES) {
      const responses: string[] = [];
      page.on('response', r => responses.push(`${r.status()} ${r.url()}`));
      await page.goto(route);
      await expect(page, `${route} should land on /login`).toHaveURL(/\/login(\?|$)/);

      // No dashboard chrome or data rendered on the way.
      await expect(page.getByRole('navigation', {name: 'Dashboard sections'})).toHaveCount(0);
      await expect(page.getByRole('button', {name: 'Scan now'})).toHaveCount(0);
      const body = await page.textContent('body');
      expect(body ?? '').not.toContain('fixture/repository');
      expect(body ?? '').not.toContain('Sign out');
      page.removeAllListeners('response');
    }
  });

  test('a protected API route still returns 401 without a session', async ({page}) => {
    // Backend releases list is session-bound.
    expect((await page.request.get(`${API}/api/releases`)).status()).toBe(401);
    // ...and so is the console's own mutation proxy.
    expect((await page.request.post('/api/scans')).status()).toBe(401);
  });
});
