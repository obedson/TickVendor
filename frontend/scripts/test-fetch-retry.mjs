import assert from'node:assert/strict';
import{fetchWithRetry}from'../src/fetchWithRetry.ts';

let attempts=0;
const response=await fetchWithRetry('/events',{},async()=>{attempts+=1;if(attempts<3)throw new TypeError('offline');return new Response('ok',{status:200})},async()=>{});
assert.equal(response.status,200);assert.equal(attempts,3);

attempts=0;
const unavailable=await fetchWithRetry('/events',{},async()=>{attempts+=1;return new Response('busy',{status:503})},async()=>{});
assert.equal(unavailable.status,503);assert.equal(attempts,3);

attempts=0;
const badRequest=await fetchWithRetry('/events',{},async()=>{attempts+=1;return new Response('bad',{status:400})},async()=>{});
assert.equal(badRequest.status,400);assert.equal(attempts,1);

await assert.rejects(()=>fetchWithRetry('/orders',{method:'POST'},async()=>{throw new TypeError('offline')},async()=>{}));
console.log('safe request retry passed');
