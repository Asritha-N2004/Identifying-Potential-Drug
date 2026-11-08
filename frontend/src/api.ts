export async function api<T=any>(path:string,body?:unknown):Promise<T>{
  const response=await fetch('/api'+path,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json',...(sessionStorage.getItem('apiKey')?{'X-API-Key':sessionStorage.getItem('apiKey')!}:{})},body:JSON.stringify(body)});
  if(!response.ok){let message;try{message=(await response.json()).detail}catch{message=response.statusText}throw Error(typeof message==='string'?message:JSON.stringify(message))}
  return response.json();
}
export async function waitForJob(id:string,onStatus:(status:string)=>void){
  for(let i=0;i<600;i++){
    const job=await api('/agents/status/'+id);onStatus(job.status);
    if(job.status==='complete')return job;
    if(job.status==='failed')throw Error(job.error||'Job failed');
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  throw Error('Job is still executing. Reopen it with its job identifier.');
}
