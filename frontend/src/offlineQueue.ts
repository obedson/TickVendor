export type QueuedAction={kind:'notification-read';resourceId:string};
export interface QueueStorage{load():Promise<QueuedAction[]>;save(items:QueuedAction[]):Promise<void>}
type Fetcher=(input:RequestInfo|URL,init?:RequestInit)=>Promise<Response>;
const KEY='tickvendor-nonsensitive-actions';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const browserQueueStorage:QueueStorage={load:async()=>{try{return JSON.parse(localStorage.getItem(KEY)??'[]')as QueuedAction[]}catch{return[]}},save:async items=>localStorage.setItem(KEY,JSON.stringify(items.slice(-100)))};
export async function enqueueAction(action:QueuedAction,storage:QueueStorage=browserQueueStorage):Promise<void>{if(!UUID.test(action.resourceId))throw new Error('Invalid queued resource identifier');const items=await storage.load();if(!items.some(item=>item.kind===action.kind&&item.resourceId===action.resourceId))items.push(action);await storage.save(items)}
export async function flushActions(storage:QueueStorage=browserQueueStorage,fetcher:Fetcher=fetch):Promise<void>{const items=await storage.load();const remaining:QueuedAction[]=[];for(const item of items){try{const response=await fetcher(`/api/v1/notifications/${item.resourceId}/read`,{method:'POST',credentials:'include'});if(!response.ok&&response.status>=500)remaining.push(item)}catch{remaining.push(item)}}await storage.save(remaining)}
