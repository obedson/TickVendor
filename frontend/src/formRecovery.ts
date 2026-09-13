import { useEffect, useRef, useState, type SetStateAction } from 'react';

export function draftOwner(): string {
  try { return JSON.parse(sessionStorage.getItem('tickvendor.session') || '{}').user?.id || ''; } catch { return ''; }
}
export function draftScope(owner: string, context: string) { return owner && context ? `draft-v1:${owner}:${context}` : ''; }

// Same encrypted-at-rest browser model as the private offline wallet. Keys are
// non-exportable; no token/password is copied into a draft. Same-origin XSS is
// outside this storage boundary. Drafts never hydrate a different user/context.
async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => { const r = indexedDB.open('tickvendor-form-drafts', 1); r.onupgradeneeded = () => r.result.createObjectStore('drafts'); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
}
async function read(db: IDBDatabase, scope: string): Promise<any> {
  return new Promise((resolve, reject) => { const r = db.transaction('drafts').objectStore('drafts').get(scope); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
}
async function write(scope: string, value: unknown) {
  const db = await database();
  try {
    const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(JSON.stringify(value)));
    await new Promise<void>((resolve, reject) => { const t = db.transaction('drafts', 'readwrite'); t.objectStore('drafts').put({ key, iv, ciphertext }, scope); t.oncomplete = () => resolve(); t.onerror = () => reject(t.error); });
  } finally { db.close(); }
}
export function useDraftState<T>(context: string, initial: T) {
  const scope = draftScope(draftOwner(), context);
  const [state, setState] = useState<T>(initial);
  const [loaded, setLoaded] = useState('');
  const [error, setError] = useState('');
  const chain = useRef(Promise.resolve());
  const generation = useRef(0);
  const current = useRef(initial);
  const pending = useRef(0);
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (pending.current) { event.preventDefault(); event.returnValue = ''; } }; window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn); }, []);
  useEffect(() => {
    let active = true; const version = ++generation.current;
    setLoaded(''); setState(initial); current.current = initial; setError('');
    if (!scope) return;
    void (async () => {
      await chain.current;
      const db = await database();
      try { const saved = await read(db, scope); if (saved) { const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: saved.iv }, saved.key, saved.ciphertext); if (active && generation.current === version) { current.current = JSON.parse(new TextDecoder().decode(plain)); setState(current.current); } } }
      finally { db.close(); }
    })().catch(() => { if (active) setError('Draft recovery unavailable. Keep this form open until submission succeeds.'); }).finally(() => { if (active) setLoaded(scope); });
    return () => { active = false; };
  }, [scope]);
  const set = (next: SetStateAction<T>) => {
    if (!scope || loaded !== scope) return;
    const value = typeof next === 'function' ? (next as (value: T) => T)(current.current) : next;
    current.current = value; setState(value); pending.current++;
    chain.current = chain.current.then(() => write(scope, value))
      .catch(() => setError('Draft could not be saved. Keep this form open.'))
      .finally(() => { pending.current--; });
  };
  const clear = async () => {
    await chain.current;
    if (scope) { const db = await database(); try { await new Promise<void>((resolve, reject) => { const t = db.transaction('drafts', 'readwrite'); t.objectStore('drafts').delete(scope); t.oncomplete = () => resolve(); t.onerror = () => reject(t.error); }); } finally { db.close(); } }
    current.current = initial; setState(initial);
  };
  return { value: loaded === scope ? state : initial, set, clear, flush: () => chain.current, ready: Boolean(scope) && loaded === scope, error };
}
