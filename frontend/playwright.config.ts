import { existsSync } from 'node:fs';
import { defineConfig } from '@playwright/test';

const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? (existsSync(macChrome) ? macChrome : undefined);
const apiURL = 'http://127.0.0.1:18000';
const webURL = 'http://127.0.0.1:13000';

export default defineConfig({
  testDir: './e2e',
  webServer: [
    {
      command: '../.venv/bin/uvicorn tests.e2e_app:app --app-dir .. --host 127.0.0.1 --port 18000',
      url: `${apiURL}/health`,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --hostname 127.0.0.1 --port 13000',
      url: webURL,
      reuseExistingServer: false,
      env: { RELEASE_MANAGER_API_URL: apiURL },
    },
  ],
  use: { baseURL: webURL, launchOptions: { executablePath } },
});
