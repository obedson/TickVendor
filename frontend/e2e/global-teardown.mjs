import { rmSync } from 'node:fs';
import { resolve } from 'node:path';

const database = resolve(import.meta.dirname, '../../.tmp-e2e.db');

export default async function globalTeardown() {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    try {
      rmSync(database, { force: true });
      return;
    } catch (error) {
      if (attempt === 24) {
        process.stderr.write(`E2E database cleanup warning: ${error.message}\n`);
        return;
      }
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
    }
  }
}