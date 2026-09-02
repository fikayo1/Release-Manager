import { spawn, ChildProcess } from 'node:child_process';
import { join } from 'node:path';
import { LOG_DIR } from './logs';

/**
 * An extra `uvicorn tests.e2e_app:app` process on a dedicated port and operator
 * database path, used by the C3 restart scenario. `E2E_KEEP_DB=1` means a
 * respawned process on the same path keeps the data the previous one wrote.
 */
export class BackendProcess {
  private proc: ChildProcess | null = null;
  readonly origin: string;

  constructor(readonly port: number, readonly dbPath: string) {
    this.origin = `http://127.0.0.1:${port}`;
  }

  async start(): Promise<void> {
    const log = join(LOG_DIR, `backend-${this.port}.log`);
    this.proc = spawn('node', [
      'e2e/support/run-logged.mjs', log, '--',
      '../.venv/bin/uvicorn', 'tests.e2e_app:app', '--app-dir', '..',
      '--host', '127.0.0.1', '--port', String(this.port),
    ], {
      stdio: 'inherit',
      env: { ...process.env, E2E_DB: this.dbPath, E2E_KEEP_DB: '1', E2E_API_PORT: String(this.port) },
    });
    await this.waitForHealth();
  }

  private async waitForHealth(): Promise<void> {
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        const response = await fetch(`${this.origin}/health`);
        if (response.ok) return;
      } catch {
        // not up yet
      }
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    throw new Error(`backend on ${this.origin} never became healthy`);
  }

  async stop(): Promise<void> {
    const proc = this.proc;
    this.proc = null;
    if (!proc || proc.exitCode !== null) return;
    await new Promise<void>((resolve) => {
      const done = setTimeout(() => { try { proc.kill('SIGKILL'); } catch {} resolve(); }, 4000);
      proc.once('exit', () => { clearTimeout(done); resolve(); });
      proc.kill('SIGTERM');
    });
  }
}
