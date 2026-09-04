import {test, expect, Page} from '@playwright/test';

async function operationCount(page: Page) {
  const response = await page.request.get('http://127.0.0.1:18000/api/operations');
  return (await response.json()).length;
}

async function signIn(page: Page) {
  await page.goto('/login');
  if (page.url().includes('/dashboard')) return;
  await page.getByRole('link', {name: 'Login with GitHub'}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function connectAndSelect(page: Page) {
  await signIn(page);
  await page.goto('/dashboard/settings/github');
  if (!await page.getByText('Connected as').count()) {
    await page.getByRole('link', {name: 'Login with GitHub'}).click();
    await expect(page.getByText('Connected as')).toBeVisible();
  }
  if (await page.getByLabel('Repository').inputValue() === 'fixture/repository-a') return;
  await page.getByLabel('Repository').selectOption('fixture/repository-a');
  await page.getByRole('button', {name:'Save repository'}).click();
  await expect(page.getByRole('status')).toContainText('Saved fixture/repository-a');
}

test.describe.serial('operator workflow', () => {
  test('OAuth callback rejects a missing state', async ({page}) => {
    await page.goto('http://127.0.0.1:18000/auth/github/callback?code=accepted');
    await expect(page).toHaveURL(/\/login\?error=invalid_state/);
    await expect(page.getByText('The sign-in request expired or was invalid. Start again.')).toBeVisible();
  });

  test('OAuth callback rejects an arbitrary incorrect state', async ({page}) => {
    await page.request.get('http://127.0.0.1:18000/auth/github', {maxRedirects: 0});
    await page.goto('http://127.0.0.1:18000/auth/github/callback?state=arbitrary-incorrect-state&code=accepted');
    await expect(page).toHaveURL(/\/login\?error=invalid_state/);
    await expect(page.getByText('The sign-in request expired or was invalid. Start again.')).toBeVisible();
  });

  test('OAuth connects, lists paginated repositories, and persists a selection', async ({page}) => {
    await signIn(page);
    await page.goto('/dashboard/settings/github');
    await expect(page.getByText('Connected as')).toBeVisible();
    await expect(page.getByLabel('Repository').locator('option'))
      .toContainText(['Select a repository', 'fixture/repository-a (private)', 'fixture/repository-b']);

    const save = page.getByRole('button', {name:'Save repository'});
    await expect(async () => {
      await page.getByLabel('Repository').selectOption('fixture/repository-a');
      await expect(save).toBeEnabled({timeout: 1000});
    }).toPass();
    await save.click();
    await expect(page.getByRole('status')).toContainText('Saved fixture/repository-a');
    await page.reload();
    await expect(page.getByLabel('Repository')).toHaveValue('fixture/repository-a');

    await page.goto('/dashboard');
    await page.getByRole('button', {name:'Scan now'}).click();
    await expect(page.getByRole('status')).toContainText('draft_created');
  });

  test('desktop navigation is read-only and manual scan creates a draft', async ({page}) => {
    await connectAndSelect(page);
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', {name: 'Release overview'})).toBeVisible();
    const before = await operationCount(page);
    await page.reload(); await page.reload();
    await expect.poll(() => operationCount(page)).toBe(before);

    await page.getByRole('link', {name: 'Releases', exact: true}).click();
    await expect(page).toHaveURL(/\/dashboard\/releases$/);
    await expect(page.getByRole('heading', {name: 'Release packs'})).toBeVisible();
    await page.waitForTimeout(250);
    await page.getByRole('link', {name: 'Operations'}).click();
    await expect(page.getByRole('heading', {name: 'Operations'})).toBeVisible();
    await page.waitForTimeout(250);
    await page.goBack(); await expect(page).toHaveURL(/\/dashboard\/releases$/);
    await page.goForward(); await expect(page).toHaveURL(/\/dashboard\/operations$/);
    await expect.poll(() => operationCount(page)).toBe(before);

    await page.goto('/dashboard');
    await page.getByRole('button', {name: 'Scan now'}).click();
    await expect(page.getByRole('status')).toContainText('draft_created');
    await expect.poll(() => operationCount(page)).toBe(before + 1);
    await page.goto('/dashboard/releases');
    const release = page.locator('tbody a').first();
    await expect(release).toBeVisible();
    await release.click();
    await expect(page.getByRole('heading', {name: 'Rationale'})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Evidence'})).toBeVisible();
    await expect(page.getByRole('link', {name: 'feat: add deterministic dashboard'})).toBeVisible();
    await page.reload();
    await expect.poll(() => operationCount(page)).toBe(before + 1);
  });

  test('schedule validates, persists, disables, and reports heartbeat', async ({page}) => {
    await connectAndSelect(page);
    await page.goto('/dashboard/settings/schedule');
    await page.getByLabel('Cron expression (UTC)').fill('bad cron');
    await page.getByRole('button', {name: 'Save schedule'}).click();
    await expect(page.getByRole('status')).toContainText('valid five-field');
    await page.getByLabel('Cron expression (UTC)').fill('*/5 * * * *');
    await page.getByLabel('Enabled').check();
    await page.getByRole('button', {name: 'Save schedule'}).click();
    await expect(page.getByRole('status')).toContainText('Schedule saved');
    await page.reload();
    await expect(page.getByLabel('Cron expression (UTC)')).toHaveValue('*/5 * * * *');
    await expect(page.getByLabel('Enabled')).toBeChecked();
    await expect(page.getByText(/Heartbeat:/)).not.toContainText('—');
    await page.getByLabel('Enabled').uncheck();
    await page.getByRole('button', {name: 'Save schedule'}).click();
    await page.reload();
    await expect(page.getByLabel('Enabled')).not.toBeChecked();
  });

  test('approval validates and publishes with an audit receipt', async ({page}) => {
    await connectAndSelect(page);
    await page.goto('/dashboard/releases');
    await page.locator('tbody a').first().click();
    await page.getByRole('button', {name: 'Approve and publish'}).click();
    await expect(page.getByText('Actor and reason are required')).toBeVisible();
    await page.getByLabel('Actor').fill('alice');
    await page.getByLabel('Reason').fill('Evidence reviewed');
    await page.getByRole('button', {name: 'Approve and publish'}).click();
    await expect(page.getByText('published', {exact: true})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Audit timeline'})).toBeVisible();
    await expect(page.getByText('publish success', {exact: true})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Human decision'})).toHaveCount(0);
  });

  test('mobile routes remain usable', async ({page}) => {
    await connectAndSelect(page);
    await page.setViewportSize({width: 390, height: 844});
    for (const [path, title] of [
      ['/dashboard', 'Release overview'],
      ['/dashboard/releases', 'Release packs'],
      ['/dashboard/operations', 'Operations'],
      ['/dashboard/settings/schedule', 'UTC scan schedule'],
    ]) {
      await page.goto(path);
      await expect(page.getByRole('heading', {name: title})).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    }
  });
});
