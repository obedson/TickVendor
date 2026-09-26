import assert from 'node:assert/strict';
import {access, readFile} from 'node:fs/promises';

const manifest = JSON.parse(await readFile(new URL('../public/manifest.webmanifest', import.meta.url), 'utf8'));
assert.equal(manifest.display, 'standalone');
assert.deepEqual(manifest.icons?.map(icon => icon.sizes), ['192x192', '512x512']);
for (const icon of manifest.icons) await access(new URL(`../public${icon.src}`, import.meta.url));
assert.ok(manifest.icons.some(icon => icon.purpose.includes('maskable')));
for (const size of [32, 180, 192, 512]) {
  const png = await readFile(new URL(`../public/tickvendor-icon-v1-${size}.png`, import.meta.url));
  assert.equal(png.subarray(1, 4).toString(), 'PNG');
  assert.equal(png.readUInt32BE(16), size);
  assert.equal(png.readUInt32BE(20), size);
  assert.ok(png.length > 500, 'Icon must not be a solid-color placeholder');
}
const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
assert.match(html, /rel="apple-touch-icon".*tickvendor-icon-v1-180.png/);
assert.match(html, /rel="icon".*tickvendor-icon-v1-32.png/);

const app = await readFile(new URL('../src/main.tsx', import.meta.url), 'utf8');
assert.match(app, /beforeinstallprompt/);
const shell = await readFile(new URL('../src/AppShell.tsx', import.meta.url), 'utf8');
assert.match(shell, /Install TickVendor/);
assert.match(app, /prompt\(\)/);

console.log('PWA installation assets and prompt passed');
