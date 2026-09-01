import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
const required = [
  '@media(max-width:650px)',
  'overflow-x:auto',
  'min-width:0',
  'focus-visible',
  '.responsive-table',
  '.form-grid',
  '.dialog-panel',
];
for (const rule of required) {
  if (!css.includes(rule)) throw new Error(`responsive policy missing: ${rule}`);
}
console.log('responsive layout policy passed');
