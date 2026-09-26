export type OfflineTicket={id?:string;public_id:string;qr_token:string;status:string;attendee_id?:string;event_id?:string;ticket_type_id?:string;used_at?:string|null;event_title?:string;event_starts_at?:string;event_ends_at?:string;venue_name?:string|null;ticket_type_name?:string;
// Individual-ticket facts the wallet now carries: who bought it, which order issued it, whether
// anyone holds it yet, and the holder's own attendance. Cached offline so a ticket still explains
// itself with no signal. `order_id` is not new data: `TicketWalletResponse` inherits it from
// `TicketResponse` and `GET /tickets/me` copies it onto every row, so the encrypted snapshot has
// always stored it. Declaring it here is what lets a caller read it at all.
group?:string;purchaser_id?:string|null;order_id?:string|null;assignment_state?:string;transfer_state?:string;self_check_in_enabled?:boolean;self_checkout_enabled?:boolean;checked_in_at?:string|null;checked_out_at?:string|null;duration_seconds?:number|null;attendance_status?:string|null;attendance_decision_reason?:string|null};
export type EncryptedTickets={iv:ArrayBuffer;ciphertext:ArrayBuffer};
type CryptoProvider=Pick<Crypto,'getRandomValues'|'subtle'>;

const DATABASE='tickvendor-private-offline';
const STORE='ticket-wallet';
// Version the encrypted snapshot so clients cannot revive reservation artifacts
// cached before the wallet's admission-history filtering was corrected.
const RECORD='current-wallet-v2';

export async function encryptTickets(tickets:OfflineTicket[],key:CryptoKey,cryptoProvider:CryptoProvider=crypto):Promise<EncryptedTickets>{
  const iv=cryptoProvider.getRandomValues(new Uint8Array(12));
  const plaintext=new TextEncoder().encode(JSON.stringify(tickets));
  const ciphertext=await cryptoProvider.subtle.encrypt({name:'AES-GCM',iv},key,plaintext);
  return{iv:iv.buffer as ArrayBuffer,ciphertext};
}

export async function decryptTickets(payload:EncryptedTickets,key:CryptoKey,cryptoProvider:CryptoProvider=crypto):Promise<OfflineTicket[]>{
  const plaintext=await cryptoProvider.subtle.decrypt({name:'AES-GCM',iv:payload.iv},key,payload.ciphertext);
  return JSON.parse(new TextDecoder().decode(plaintext)) as OfflineTicket[];
}

function openDatabase():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const request=indexedDB.open(DATABASE,1);request.onupgradeneeded=()=>request.result.createObjectStore(STORE);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)})}
function complete(transaction:IDBTransaction):Promise<void>{return new Promise((resolve,reject)=>{transaction.oncomplete=()=>resolve();transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error)})}
function readRecord<T>(database:IDBDatabase,key:string):Promise<T|undefined>{return new Promise((resolve,reject)=>{const request=database.transaction(STORE).objectStore(STORE).get(key);request.onsuccess=()=>resolve(request.result as T|undefined);request.onerror=()=>reject(request.error)})}

export async function cacheTicketWallet(tickets:OfflineTicket[]):Promise<void>{
  const database=await openDatabase();
  try{
    const key=await crypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt']);
    const payload=await encryptTickets(tickets,key);
    const transaction=database.transaction(STORE,'readwrite');
    const store=transaction.objectStore(STORE);
    store.put(key,'key');store.put(payload,RECORD);
    await complete(transaction);
  }finally{database.close()}
}

export async function loadCachedTicketWallet():Promise<OfflineTicket[]>{
  const database=await openDatabase();
  try{
    const key=await readRecord<CryptoKey>(database,'key');
    const payload=await readRecord<EncryptedTickets>(database,RECORD);
    if(!key||!payload)return[];
    return await decryptTickets(payload,key);
  }catch{return[]}
  finally{database.close()}
}

export async function clearCachedTicketWallet():Promise<void>{
  const database=await openDatabase();
  try{const transaction=database.transaction(STORE,'readwrite');transaction.objectStore(STORE).clear();await complete(transaction)}finally{database.close()}
}
