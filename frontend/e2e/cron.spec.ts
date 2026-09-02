import {test, expect} from '@playwright/test';

const API = 'http://127.0.0.1:18000';
const SECRET = 'cron-fixed-browser-test-secret';

test('cron proxy rejects missing proof without backend work', async ({request}) => {
  await request.post(`${API}/test/github/journal/reset`);
  expect((await request.post('/api/cron/scheduler')).status()).toBe(401);
  expect((await request.post('/api/cron/scheduler', {headers: {authorization: `Bearer ${SECRET}`}})).status()).toBe(401);
  expect((await request.post('/api/cron/scheduler', {
    headers: {authorization: `Bearer ${SECRET}`, 'x-vercel-cron': 'arbitrary-marker'},
  })).status()).toBe(401);
  const journal = await (await request.get(`${API}/test/github/journal`)).json();
  expect(journal.entries).toEqual([]);
});

test('a Vercel GET cron invocation calls the serverless tick idempotently', async ({request}) => {
  const headers = {authorization: `Bearer ${SECRET}`, 'user-agent': 'vercel-cron/1.0'};
  const first = await request.get('/api/cron/scheduler', {headers});
  const second = await request.get('/api/cron/scheduler', {headers});
  expect(first.ok()).toBeTruthy();
  expect(second.ok()).toBeTruthy();
  const operations = await (await request.get(`${API}/api/operations`)).json();
  const scheduled = operations.filter((item: {source: string}) => item.source === 'scheduled');
  expect(scheduled.length).toBeLessThanOrEqual(1);
});
