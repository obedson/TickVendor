import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {decryptTickets, encryptTickets} from '../src/offlineTickets.ts';

const tickets = [{public_id:'TICKET-1',qr_token:'secret-qr-token',status:'active'}];
const key = await webcrypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt']);
const encrypted = await encryptTickets(tickets,key,webcrypto);
assert.notEqual(new TextDecoder().decode(encrypted.ciphertext),'secret-qr-token');
assert.deepEqual(await decryptTickets(encrypted,key,webcrypto),tickets);

const wrongKey = await webcrypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt']);
await assert.rejects(()=>decryptTickets(encrypted,wrongKey,webcrypto));
console.log('offline ticket encryption passed');
