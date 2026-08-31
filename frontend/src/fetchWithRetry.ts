type Fetcher=(input:RequestInfo|URL,init?:RequestInit)=>Promise<Response>;
type Sleeper=(milliseconds:number)=>Promise<void>;
const RETRYABLE_STATUS=new Set([408,425,429,500,502,503,504]);

export async function fetchWithRetry(input:RequestInfo|URL,init:RequestInit={},fetcher:Fetcher=fetch,sleep:Sleeper=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds))):Promise<Response>{
  const method=(init.method??'GET').toUpperCase();
  if(method!=='GET'&&method!=='HEAD')return fetcher(input,init);
  let lastError:unknown;
  for(let attempt=0;attempt<3;attempt+=1){
    try{
      const response=await fetcher(input,init);
      if(!RETRYABLE_STATUS.has(response.status)||attempt===2)return response;
    }catch(error){
      lastError=error;
      if(attempt===2)throw error;
    }
    await sleep(250*2**attempt);
  }
  throw lastError;
}
