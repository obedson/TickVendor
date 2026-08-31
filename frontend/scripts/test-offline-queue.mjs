import assert from'node:assert/strict';
import{enqueueAction,flushActions}from'../src/offlineQueue.ts';
class MemoryStorage{items=[];load(){return Promise.resolve(this.items)}save(items){this.items=items;return Promise.resolve()}}
const storage=new MemoryStorage();
await enqueueAction({kind:'notification-read',resourceId:'11111111-1111-4111-8111-111111111111'},storage);
await enqueueAction({kind:'notification-read',resourceId:'11111111-1111-4111-8111-111111111111'},storage);
assert.equal(storage.items.length,1,'duplicate idempotent actions should collapse');
await assert.rejects(()=>enqueueAction({kind:'notification-read',resourceId:'not-an-id'},storage));
let calls=0;await flushActions(storage,async()=>{calls+=1;return new Response(null,{status:204})});assert.equal(calls,1);assert.equal(storage.items.length,0);
await enqueueAction({kind:'notification-read',resourceId:'22222222-2222-4222-8222-222222222222'},storage);
await flushActions(storage,async()=>new Response(null,{status:503}));assert.equal(storage.items.length,1,'transient failures should remain queued');
console.log('offline action queue passed');
