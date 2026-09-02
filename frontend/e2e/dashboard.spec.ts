import {test, expect, Page} from '@playwright/test';

async function operationCount(page: Page) {
  const response = await page.request.get('http://127.0.0.1:18000/api/operations');
  return (await response.json()).length;
}

test.describe.serial('operator workflow', () => {
  test('OAuth callback rejects a missing state', async ({page}) => {
    await page.goto('http://127.0.0.1:18000/auth/github/callback?code=accepted');
    await expect(page).toHaveURL(/settings\/github\?github=invalid_state/);
    await expect(page.getByText('The authorization request expired or was invalid. Try again.')).toBeVisible();
  });

  test('OAuth callback rejects an arbitrary incorrect state', async ({page}) => {
    // Start authorization to establish a signed session, then substitute an
    // unrelated state rather than using the state returned by the server.
    await page.request.get('http://127.0.0.1:18000/auth/github', {maxRedirects: 0});
    await page.goto('http://127.0.0.1:18000/auth/github/callback?state=arbitrary-incorrect-state&code=accepted');
    await expect(page).toHaveURL(/settings\/github\?github=invalid_state/);
    await expect(page.getByText('The authorization request expired or was invalid. Try again.')).toBeVisible();
  });

  test('OAuth state, paginated repository authorization, persistence, and release targeting', async ({page}) => {
    const seen: string[] = [];
    page.on('request', request => {
      if(request.url().includes('/test/github/authorize')) seen.push(new URL(request.url()).searchParams.get('state') || '');
    });
    await page.goto('/settings/github');
    await page.getByRole('link', {name:'Continue with GitHub'}).click();
    await expect(page).toHaveURL(/settings\/github\?github=connected/);
    await expect(page.getByText('Connected as')).toBeVisible();
    expect(seen[0]).toBeTruthy();

    // A consumed state cannot be replayed, and a fresh denial is explicit.
    await page.goto(`http://127.0.0.1:18000/auth/github/callback?state=${seen[0]}&code=accepted`);
    await expect(page).toHaveURL(/github=invalid_state/);
    const fresh = await page.request.get('http://127.0.0.1:18000/auth/github', {maxRedirects:0});
    const denial = new URL(fresh.headers().location); denial.searchParams.set('error','1');
    await page.goto(denial.toString());
    await expect(page).toHaveURL(/github=denied/);

    await page.getByLabel('Repository').selectOption('fixture/repository-a');
    await page.getByRole('button', {name:'Save repository'}).click();
    await expect(page.getByRole('status')).toContainText('Saved fixture/repository-a');
    await page.reload();
    await expect(page.getByLabel('Repository')).toHaveValue('fixture/repository-a');
    const forbidden = await page.request.put('http://127.0.0.1:18000/api/github/repository', {data:{full_name:'other/secret'}});
    expect(forbidden.status()).toBe(422);

    await page.goto('/');
    await page.getByRole('button', {name:'Scan now'}).click();
    await expect(page.getByRole('status')).toContainText('draft_created');
    await page.goto('/settings/github');
    await page.getByLabel('Repository').selectOption('fixture/repository-b');
    await page.getByRole('button', {name:'Save repository'}).click();
    await page.goto('/releases');
    await page.locator('tbody a').first().click();
    await page.getByLabel('Actor').fill('oauth-reviewer');
    await page.getByLabel('Reason').fill('Repository target verified');
    await page.getByRole('button', {name:'Approve and publish'}).click();
    await expect(page.getByText('published', {exact:true})).toBeVisible();
    const publications = await (await page.request.get('http://127.0.0.1:18000/test/publications')).json();
    expect(publications.at(-1).repository).toBe('fixture/repository-a');
  });

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
