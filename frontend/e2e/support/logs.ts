import { join } from 'node:path';

// Playwright always runs with cwd = frontend/. The webServer commands tee their
// combined stdout+stderr here; oauth.spec.ts asserts the token canary is absent.
export const LOG_DIR = join(process.cwd(), 'e2e/.logs');
export const BACKEND_LOG = join(LOG_DIR, 'backend.log');
export const FRONTEND_LOG = join(LOG_DIR, 'frontend.log');
