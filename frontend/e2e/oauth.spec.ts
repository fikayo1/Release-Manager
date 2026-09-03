import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {BACKEND_LOG, FRONTEND_LOG} from './support/logs';

// Must equal tests/fakes.py::CANARY_TOKEN.
const SECRETS = [
  'ghp_FaKeCaNaRy0000NeverLogMe0000DEADBEEFcafe',
  'oauth-client-secret-browser-canary',
  'cron-fixed-browser-test-secret',
  'postgres://user:database-url-browser-canary@db.invalid/release',
  'database-url-browser-canary',
];
const API = 'http://127.0.0.1:18000';

test.describe.serial('OAuth acceptance (C1, C2)', () => {
  test('authorizes through deterministic doubles and keeps the token off the browser', async ({page}) => {
    const requestUrls: string[] = [];
    const responseBodies: string[] = [];
    const consoleLines: string[] = [];
    page.on('request', r => requestUrls.push(r.url()));
    page.on('console', m => consoleLines.push(m.text()));
    page.on('response', async r => { try { responseBodies.push(await r.text()); } catch { /* opaque */ } });

    // Initiate OAuth through the same-origin route the "Continue with GitHub"
    // link targets. Re-authorising is idempotent.
    await page.goto('/login');
    await page.request.post(`${API}/test/github/journal/reset`);
    await page.goto('/auth/github');
    await expect(page).toHaveURL(/\/dashboard$/);

    // Repository selection now lives on the dashboard settings route.
    await page.goto('/dashboard/settings/github');
    await expect(page.getByText('Connected as')).toBeVisible();

    const select = page.getByLabel('Repository');
    await expect(select.locator('option')).toContainText([
      'Select a repository', 'fixture/repository-a (private)', 'fixture/repository-b',
    ]);
    const save = page.getByRole('button', {name: 'Save repository'});
    await expect(async () => {
      await select.selectOption('fixture/repository-a');
      await expect(save).toBeEnabled({timeout: 1000});
    }).toPass();
    await save.click();
    await expect(page.getByRole('status')).toContainText('Saved fixture/repository-a');

    // C1: the journal shows only the offline authorize/token + repository-list calls.
    const journal = await (await page.request.get(`${API}/test/github/journal`)).json();
    const kinds = journal.entries.map((e: {kind: string}) => e.kind);
    expect(kinds.slice(0, 3)).toEqual(['authorize', 'token_exchange', 'user']);
    expect([...new Set(kinds)].sort()).toEqual(['authorize', 'repos_page', 'token_exchange', 'user']);
    expect(journal.repositories).toEqual([]);

    // C2: capture everything the browser can observe, plus the captured server logs.
    const html = await page.content();
    const storage = await page.evaluate(() => JSON.stringify([
      Object.entries(localStorage), Object.entries(sessionStorage),
    ]));
    const documentCookie = await page.evaluate(() => document.cookie);

    const haystacks: Record<string, string> = {
      'address bar': page.url(),
      'browser request URLs': requestUrls.join('\n'),
      'browser response bodies': responseBodies.join('\n'),
      'rendered HTML': html,
      'local/session storage': storage,
      'console output': consoleLines.join('\n'),
      'captured backend log': readFileSync(BACKEND_LOG, 'utf8'),
      'captured frontend log': readFileSync(FRONTEND_LOG, 'utf8'),
    };
    for (const [where, value] of Object.entries(haystacks)) {
      for (const secret of SECRETS) {
        expect(value, `server secret must be absent from ${where}`).not.toContain(secret);
      }
    }

    // The session cookie stays HttpOnly and never appears in any request URL.
    expect(documentCookie).not.toContain('release_manager_session');
    expect(requestUrls.some(u => u.includes('release_manager_session'))).toBe(false);
  });
});
