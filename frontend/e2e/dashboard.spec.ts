import {test, expect, Page} from '@playwright/test';

async function operationCount(page: Page) {
  const response = await page.request.get('http://127.0.0.1:18000/api/operations');
  return (await response.json()).length;
}

test.describe.serial('operator workflow', () => {
  test('desktop navigation is read-only and manual scan creates a draft', async ({page}) => {
    await page.goto('/');
    await expect(page.getByRole('heading', {name: 'Release overview'})).toBeVisible();
    const before = await operationCount(page);
    await page.reload(); await page.reload();
    await expect.poll(() => operationCount(page)).toBe(before);

    await page.getByRole('link', {name: 'Releases', exact: true}).click();
    await expect(page).toHaveURL(/\/releases$/);
    await expect(page.getByRole('heading', {name: 'Release packs'})).toBeVisible();
    await page.waitForTimeout(250);
    await page.getByRole('link', {name: 'Operations'}).click();
    await expect(page.getByRole('heading', {name: 'Operations'})).toBeVisible();
    await page.waitForTimeout(250);
    await page.goBack(); await expect(page).toHaveURL(/\/releases$/);
    await page.goForward(); await expect(page).toHaveURL(/\/operations$/);
    await expect.poll(() => operationCount(page)).toBe(before);

    await page.goto('/');
    await page.getByRole('button', {name: 'Scan now'}).click();
    await expect(page.getByRole('status')).toContainText('draft_created');
    await expect.poll(() => operationCount(page)).toBe(before + 1);
    await page.goto('/releases');
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
    await page.goto('/settings/schedule');
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
    await page.goto('/releases');
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
    await page.setViewportSize({width: 390, height: 844});
    for (const [path, title] of [['/', 'Release overview'], ['/releases', 'Release packs'], ['/operations', 'Operations'], ['/settings/schedule', 'UTC scan schedule']]) {
      await page.goto(path);
      await expect(page.getByRole('heading', {name: title})).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    }
  });
});
