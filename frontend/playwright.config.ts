import { existsSync } from 'node:fs';
import { defineConfig } from '@playwright/test';
import { BACKEND_LOG, FRONTEND_LOG } from './e2e/support/logs';

const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? (existsSync(macChrome) ? macChrome : undefined);
const apiURL = 'http://127.0.0.1:18000';
const webURL = 'http://127.0.0.1:13000';
const secretCanaries = {
  GITHUB_OAUTH_CLIENT_SECRET: 'oauth-client-secret-browser-canary',
  CRON_SECRET: 'cron-fixed-browser-test-secret',
  // The fixture constructs explicit SQLite settings, so this can exercise leak
  // detection without requiring a live Postgres service.
  DATABASE_URL: 'postgres://user:database-url-browser-canary@db.invalid/release',
};
const logged = (logFile: string, command: string) =>
  `node e2e/support/run-logged.mjs ${logFile} -- ${command}`;

export default defineConfig({
  testDir: './e2e',
  // One shared backend + web server for the whole run: never run specs in
  // parallel against the single operator database.
  workers: 1,
  fullyParallel: false,
  webServer: [
    {
      command: logged(BACKEND_LOG,
        'env PYTHONPATH=../backend ../.venv/bin/uvicorn tests.e2e_app:app --app-dir .. --host 127.0.0.1 --port 18000'),
      url: `${apiURL}/health`,
      reuseExistingServer: false,
      env: secretCanaries,
    },
    {
      command: logged(FRONTEND_LOG, 'npm run dev -- --hostname 127.0.0.1 --port 13000'),
      url: webURL,
      reuseExistingServer: false,
      env: {
        RELEASE_MANAGER_API_URL: apiURL,
        ...secretCanaries,
      },
    },
  ],
  use: { baseURL: webURL, launchOptions: { executablePath } },
});
