// Spawn a command, tee its combined stdout+stderr to a log file, and pass the
// same output through to this process so Playwright's webServer still shows it.
// Usage: node run-logged.mjs <logfile> -- <command> [args...]
import { spawn } from 'node:child_process';
import { createWriteStream, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const separator = process.argv.indexOf('--');
const logFile = process.argv[2];
if (!logFile || separator === -1 || separator >= process.argv.length - 1) {
  console.error('usage: run-logged.mjs <logfile> -- <command> [args...]');
  process.exit(2);
}
const [command, ...args] = process.argv.slice(separator + 1);

mkdirSync(dirname(logFile), { recursive: true });
const log = createWriteStream(logFile, { flags: 'w' });

const child = spawn(command, args, { stdio: ['inherit', 'pipe', 'pipe'] });
for (const [stream, sink] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) {
  stream.on('data', (chunk) => { sink.write(chunk); log.write(chunk); });
}

const forward = (signal) => { if (!child.killed) child.kill(signal); };
process.on('SIGINT', () => forward('SIGINT'));
process.on('SIGTERM', () => forward('SIGTERM'));

child.on('exit', (code, signal) => {
  log.end(() => process.exit(signal ? 1 : code ?? 0));
});
child.on('error', (error) => {
  log.write(String(error));
  log.end(() => process.exit(1));
});
