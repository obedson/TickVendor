import assert from 'node:assert/strict';
import {access, readFile} from 'node:fs/promises';

const manifest = JSON.parse(await readFile(new URL('../public/manifest.webmanifest', import.meta.url), 'utf8'));
assert.equal(manifest.display, 'standalone');
assert.deepEqual(manifest.icons?.map(icon => icon.sizes), ['192x192', '512x512']);
for (const icon of manifest.icons) await access(new URL(`../public${icon.src}`, import.meta.url));

const app = await readFile(new URL('../src/main.tsx', import.meta.url), 'utf8');
assert.match(app, /beforeinstallprompt/);
assert.match(app, /Install TickEven/);
assert.match(app, /prompt\(\)/);

console.log('PWA installation assets and prompt passed');
