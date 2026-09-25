import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import ts from 'typescript';

const source = await readFile(new URL('../src/geolocation.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
function load(readings) {
  let calls = 0;
  const context = {
    exports: {}, require: () => ({ locationErrorMessage: e => `Location error ${e.code}` }),
    navigator: { geolocation: { getCurrentPosition(success, failure, options) {
      assert.equal(options.enableHighAccuracy, true);
      assert.equal(options.maximumAge, 0);
      const next = readings[calls++];
      if (typeof next === 'number') success({ coords: { latitude: 6.44, longitude: 7.49, accuracy: next } });
      else failure(next);
    } } }, window: { setTimeout: callback => { callback(); return 1; } },
  };
  vm.runInNewContext(javascript, context);
  return { currentPosition: context.exports.currentPosition, calls: () => calls };
}
let test = load([800, 240, 12]);
assert.equal((await test.currentPosition({ targetAccuracy: 100 })).accuracy_meters, 12);
assert.equal(test.calls(), 3);
test = load([12]);
await test.currentPosition({ targetAccuracy: 100 });
assert.equal(test.calls(), 1);
test = load([800, 300, 900]);
assert.equal((await test.currentPosition({ targetAccuracy: 100 })).accuracy_meters, 300);
test = load([800, { code: 3 }]);
assert.equal((await test.currentPosition({ targetAccuracy: 100 })).accuracy_meters, 800);
test = load([{ code: 1 }]);
await assert.rejects(test.currentPosition({ targetAccuracy: 100 }), e => e.kind === 'denied');
assert.equal(test.calls(), 1);
test = load([800, { code: 1 }]);
await assert.rejects(test.currentPosition({ targetAccuracy: 100 }), e => e.kind === 'denied');
console.log('PASS: 6 geolocation sampling and permission cases');
