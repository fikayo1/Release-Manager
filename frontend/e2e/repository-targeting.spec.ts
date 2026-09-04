import {test, expect, Page} from '@playwright/test';
import {mkdirSync, rmSync} from 'node:fs';
import {join} from 'node:path';
import {BackendProcess} from './support/backend';

const API = `http://127.0.0.1:${process.env.SHIPYARD_E2E_API_PORT ?? '18000'}`;
const A = 'fixture/repository-a';
const B = 'fixture/repository-b';

async function ensureConnected(page: Page) {
  await page.goto('/login');
  const loginLink = page.getByRole('link', {name: 'Login with GitHub'});
  if (await loginLink.isVisible().catch(() => false)) {
    await loginLink.click();
    await expect(page).toHaveURL(/\/dashboard$/);
  }
  await page.goto('/dashboard/settings/github');
  const link = page.getByRole('link', {name: 'Login with GitHub'});
  if (await link.isVisible().catch(() => false)) {
    await link.click();
    await expect(page).toHaveURL(/github=connected/);
  }
  await expect(page.getByText('Connected as')).toBeVisible();
}

async function selectRepo(page: Page, fullName: string) {
  await page.goto('/dashboard/settings/github');
  const save = page.getByRole('button', {name: 'Save repository'});
  await expect(async () => {
    await page.getByLabel('Repository').selectOption(fullName);
    await expect(save).toBeEnabled({timeout: 1000});
  }).toPass();
  await save.click();
  await expect(page.getByRole('status')).toContainText(`Saved ${fullName}`);
}

async function scanNow(page: Page) {
  await page.goto('/dashboard');
  await page.getByRole('button', {name: 'Scan now'}).click();
  await expect(page.getByRole('status')).toContainText('draft_created');
}

async function json(page: Page, path: string, init?: {method?: string; data?: unknown}) {
  const response = await page.request.fetch(`${API}${path}`, {
    method: init?.method ?? 'GET',
    data: init?.data as any,
  });
  expect(response.ok(), `${path} -> ${response.status()}`).toBeTruthy();
  return response.json();
}

test.describe.serial('repository targeting acceptance (C3-C6)', () => {
  test('C4: A->B retargets the next manual scan; existing A work stays A', async ({page}) => {
    await ensureConnected(page);
    await selectRepo(page, A);
    await scanNow(page);

    const releasesAfterA = await json(page, '/api/releases');
    const packA = await json(page, `/api/releases/${releasesAfterA[0].id}`);
    expect(packA.evidence.repository).toBe(A);

    await selectRepo(page, B);
    await page.request.post(`${API}/test/github/journal/reset`);
    await scanNow(page);

    const journal = await json(page, '/test/github/journal');
    expect(journal.repositories).toEqual([B]);
    expect(journal.entries.filter((e: {repository: string}) => e.repository === A)).toEqual([]);

    const retained = await json(page, `/api/releases/${packA.id}`);
    expect(retained.evidence.repository).toBe(A);
  });

  test('C5: the next due scheduled scan targets B exactly like the manual scan', async ({page}) => {
    await ensureConnected(page);
    await selectRepo(page, B);

    await page.goto('/dashboard/settings/schedule');
    await page.getByLabel('Cron expression (UTC)').fill('* * * * *');
    await page.getByLabel('Enabled').check();
    await page.getByRole('button', {name: 'Save schedule'}).click();
    await expect(page.getByRole('status')).toContainText('Schedule saved');

    await page.request.post(`${API}/test/github/journal/reset`);
    await json(page, '/test/scheduler/tick', {method: 'POST'});

    const operations = await json(page, '/api/operations');
    const scheduled = operations.filter((op: {source: string}) => op.source === 'scheduled');
    expect(scheduled).toHaveLength(1);
    expect(scheduled[0].repository).toBe(B);
    expect(scheduled[0].result).toBe('draft_created');

    const journal = await json(page, '/test/github/journal');
    expect(journal.repositories).toEqual([B]);
  });

  test('C6: selecting B never retargets reconcile/rollback/approval/publish of A work', async ({page}) => {
    const seeds: [string, string][] = [
      ['c6-approve', 'pending'], ['c6-reject', 'pending'],
      ['c6-publish', 'approved'], ['c6-reconcile', 'uncertain'],
    ];
    for (const [pack_id, status] of seeds) {
      await page.request.post(`${API}/test/seed`, {data: {pack_id, repository: A, status}});
    }

    await ensureConnected(page);
    await selectRepo(page, B);
    await page.request.post(`${API}/test/github/journal/reset`);

    const decision = {actor: 'oauth-reviewer', reason: 'targeting verified'};
    expect((await page.request.post(`${API}/api/packs/c6-approve/approve`, {data: decision})).ok()).toBeTruthy();
    expect((await page.request.post(`${API}/api/packs/c6-reject/reject`, {data: decision})).ok()).toBeTruthy();
    expect((await page.request.post(`${API}/api/packs/c6-publish/publish`)).ok()).toBeTruthy();
    expect((await page.request.post(`${API}/api/packs/c6-reconcile/reconcile`)).ok()).toBeTruthy();

    const journal = await json(page, '/test/github/journal');
    expect(journal.repositories).toEqual([A]);

    const publications = await json(page, '/test/publications');
    expect(publications.length).toBeGreaterThan(0);
    expect(publications.every((p: {repository: string}) => p.repository === A)).toBe(true);

    for (const [pack_id, expectedStatus] of [
      ['c6-approve', 'published'], ['c6-reject', 'rejected'],
      ['c6-publish', 'published'], ['c6-reconcile', 'retry_safe'],
    ]) {
      const detail = await json(page, `/api/releases/${pack_id}`);
      expect(detail.evidence.repository).toBe(A);
      expect(detail.status).toBe(expectedStatus);
    }
  });

  test('C3: the selected repository survives a real backend restart on the same DB file', async ({page}) => {
    const dbPath = join(process.cwd(), 'e2e/.tmp/restart.db');
    mkdirSync(join(process.cwd(), 'e2e/.tmp'), {recursive: true});
    rmSync(dbPath, {force: true});

    let backend = new BackendProcess(18010, dbPath);
    await backend.start();
    try {
      await page.goto(`${backend.origin}/auth/github`);
      await expect(page).toHaveURL(new RegExp(`${backend.origin}/dashboard$`));
      const put = await page.request.put(`${backend.origin}/api/github/repository`, {data: {full_name: A}});
      expect(put.ok()).toBeTruthy();

      const before = await (await page.request.get(`${backend.origin}/api/github`)).json();
      expect(before.selected_repository).toBe(A);

      await backend.stop();
      backend = new BackendProcess(18010, dbPath);
      await backend.start();

      const after = await (await page.request.get(`${backend.origin}/api/github`)).json();
      expect(after.status).toBe('connected');
      expect(after.selected_repository).toBe(A);
    } finally {
      await backend.stop();
    }
  });
});
