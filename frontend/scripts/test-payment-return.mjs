import assert from 'node:assert/strict';
import fs from 'node:fs';
const source=fs.readFileSync(new URL('../src/PaymentReturn.tsx',import.meta.url),'utf8');
const main=fs.readFileSync(new URL('../src/main.tsx',import.meta.url),'utf8');
// The page resolves the payment it was returned with: by local id when it has one, and by the
// provider's own reference otherwise, because a checkout that never succeeded is not reachable by
// its local id from here.
assert.match(source,/payments\/verify-reference/);
assert.match(source,/payments\/\$\{encodeURIComponent\(resolvedPaymentId\)\}/);
// The status is whatever the server reports, and each outcome lands on its own state: a cancelled
// checkout is not a failed payment, and neither is a successful one.
assert.match(source,/data\.status === 'success' \|\| data\.status === 'successful' \? 'successful'/);
assert.match(source,/data\.status === 'cancelled' \? 'cancelled'/);
assert.match(source,/data\.status === 'failed' \? 'failed'/);
assert.match(source,/cancelled: \{ icon: '🚫', title: 'Payment cancelled'/);
// Polling is bounded rather than open-ended.
assert.match(source,/attempt >= 8/);
// Cancelling asks the server to release the reservation, and the page reports what the server
// decided instead of assuming the release happened.
assert.match(source,/apiJson<any>\('payments\/cancel'/);
assert.match(source,/if \(!result\.released\)/);
// Releasing puts the tickets back on sale, so the remaining availability is read back.
assert.match(source,/events\/\$\{result\.event_id\}\/ticket-types/);
// Returning from a checkout never starts another one.
assert.doesNotMatch(source,/initialize/);
assert.match(main,/paymentId/);
assert.doesNotMatch(main,/searchParams\.get\(['"]success/);
console.log('payment return authoritative status contract passed');
