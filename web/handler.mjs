import {readFileSync} from 'node:fs';
import {configured,authenticateAccount,hasConfiguredAccount,issueSession,readSession,signedSessionUser,sessionCookie,verifyPassword} from './auth.mjs';
import {accountStore,AccountError} from './account-store.mjs';

let bundle;
const attempts=new Map();
function load(){return bundle??=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url),'utf8'))}
async function sessionUser(req){const known=readSession(req.headers.cookie);if(known)return known;const user=signedSessionUser(req.headers.cookie);return user&&await accountStore.find(user)?user:null}
function json(res,status,value){res.statusCode=status;res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','private, no-store');res.setHeader('X-Content-Type-Options','nosniff');res.end(JSON.stringify(value))}
async function body(req){
  if(req.body&&typeof req.body==='object')return req.body;
  if(typeof req.body==='string'){if(req.body.length>4096)throw Error('Invalid body');return JSON.parse(req.body)}
  let text='';for await(const chunk of req){text+=chunk;if(text.length>4096)throw Error('Invalid body')}
  return text?JSON.parse(text):{};
}
function caseJob(id){
  const [,disease,limitText]=id.split('.');const limit=Number(limitText);
  const saved=load().cases[disease];if(!saved||!Number.isInteger(limit)||limit<1||limit>100)return null;
  return {...saved.job,id,status:'complete',published_snapshot:true,result:{...saved.job.result,candidates:saved.job.result.candidates.slice(0,limit),published_snapshot:true,label:'Published computational analysis; not a new live discovery run. Experimental and clinical validation required.'}};
}

export default async function handler(req,res){
  try{
    const url=new URL(req.url,'https://'+(req.headers.host||'localhost'));
    const path='/'+(url.searchParams.get('__route')||url.pathname.replace(/^\/api\/?/,''));
    const method=req.method||'GET';
    if(method!=='GET'&&req.headers.origin&&req.headers.origin!==`https://${req.headers.host}`&&req.headers.origin!==`http://${req.headers.host}`)return json(res,403,{detail:'Cross-origin request rejected'});
    if(path==='/auth/session'&&method==='GET')return json(res,200,{user:await sessionUser(req),configured:configured(),registration_available:accountStore.enabled()});
    if(path==='/auth/register'&&method==='POST'){
      if(!configured())return json(res,503,{detail:'Workspace sign-in has not been configured'});
      const key='register:'+String(req.headers['x-forwarded-for']||req.socket?.remoteAddress||'unknown').split(',')[0];
      const now=Date.now();const history=(attempts.get(key)||[]).filter(t=>now-t<15*60*1000);
      if(history.length>=5){res.setHeader('Retry-After','900');return json(res,429,{detail:'Too many registration attempts. Try again in 15 minutes.'})}
      if(attempts.size>10000)attempts.clear();history.push(now);attempts.set(key,history);
      const username=await accountStore.register(await body(req));
      res.setHeader('Set-Cookie',sessionCookie(issueSession(username)));
      return json(res,201,{user:username});
    }
    if(path==='/auth/login'&&method==='POST'){
      if(!configured())return json(res,503,{detail:'Workspace sign-in has not been configured'});
      const key=String(req.headers['x-forwarded-for']||req.socket?.remoteAddress||'unknown').split(',')[0];
      const now=Date.now();const history=(attempts.get(key)||[]).filter(t=>now-t<15*60*1000);
      if(history.length>=8){res.setHeader('Retry-After','900');return json(res,429,{detail:'Too many sign-in attempts. Try again in 15 minutes.'})}
      if(attempts.size>10000)attempts.clear();history.push(now);attempts.set(key,history);
      const data=await body(req);
      data.username=typeof data.username==='string'?data.username.trim().toLowerCase():'';
      let valid=authenticateAccount(data.username,data.password);
      if(!valid&&!hasConfiguredAccount(data.username)){const stored=await accountStore.find(data.username);valid=Boolean(stored&&verifyPassword(data.password,stored.passwordHash))}
      if(!valid)return json(res,401,{detail:'Username or password is incorrect'});
      attempts.delete(key);res.setHeader('Set-Cookie',sessionCookie(issueSession(data.username)));
      return json(res,200,{user:data.username});
    }
    if(path==='/auth/logout'&&method==='POST'){res.setHeader('Set-Cookie',sessionCookie('',true));return json(res,200,{ok:true})}
    if(!await sessionUser(req))return json(res,401,{detail:'Please sign in to your workspace'});
    const data=load();const entities=data.dataset.entities;const edges=data.dataset.relationships;
    if(path==='/health'&&method==='GET')return json(res,200,{status:'ok',mode:'source',database:'published_snapshot',neo4j:false,trained_checkpoint:true,published_snapshot:true,graph_sha256:data.graph.sha256,snapshot_date:'2026-11-08'});
    if(path==='/graph/statistics'&&method==='GET')return json(res,200,data.graph);
    if(['/model/metrics','/models/metrics'].includes(path)&&method==='GET')return json(res,200,data.evaluation);
    if(['/models/train','/model/train','/data/ingest','/graph/build'].includes(path))return json(res,409,{detail:'This Vercel edition serves a published research snapshot. Training and ingestion require the full Python research service.'});
    if(path==='/sources')return json(res,200,{available:['Open Targets','Europe PMC'],published_snapshot:true,limitations:data.limitations});
    if(['/diseases','/diseases/search','/drugs','/drugs/search'].includes(path)&&method==='GET'){
      const kind=path.startsWith('/diseases')?'Disease':'Drug';const q=(url.searchParams.get('q')||'').toLowerCase();
      const limit=Number(url.searchParams.get('limit')||100),offset=Number(url.searchParams.get('offset')||0);
      if(q.length>300||!Number.isInteger(limit)||limit<1||limit>100||!Number.isInteger(offset)||offset<0)return json(res,422,{detail:'Invalid search pagination'});
      return json(res,200,entities.filter(e=>e.kind===kind&&(e.name+' '+e.id).toLowerCase().includes(q)).slice(offset,offset+limit));
    }
    const graph=path.match(/^\/graph\/(?:subgraph|neighbors|neighborhood)\/(.+)$/);
    if(graph&&method==='GET'){
      const id=decodeURIComponent(graph[1]);if(!entities.some(e=>e.id===id))return json(res,404,{detail:'Unknown entity'});
      const ids=new Set([id]);for(const edge of edges){if(['TREATS','INVESTIGATED_IN'].includes(edge.relation))continue;if(edge.source===id)ids.add(edge.target);if(edge.target===id)ids.add(edge.source)}
      return json(res,200,{nodes:entities.filter(e=>ids.has(e.id)),edges:edges.filter(e=>ids.has(e.source)&&ids.has(e.target))});
    }
    if(['/repurposing/predict','/predictions/run','/agents/run'].includes(path)&&method==='POST'){
      const request=await body(req);if(!data.cases[request.disease_id])return json(res,404,{detail:'No published analysis for this disease'});
      if(request.weights)return json(res,409,{detail:'Published analyses preserve their recorded scoring weights.'});
      const limit=request.limit??10;if(!Number.isInteger(limit)||limit<1||limit>100)return json(res,422,{detail:'Limit must be 1–100'});
      return json(res,202,{job_id:`published.${request.disease_id}.${limit}`,status:'complete',published_snapshot:true});
    }
    const jobRoute=path.match(/^\/(?:repurposing\/results|predictions|agents\/status|agents\/logs)\/(published\.[^.]+\.\d+)(?:\/(candidates|explanations))?$/);
    if(jobRoute&&method==='GET'){
      const job=caseJob(jobRoute[1]);if(!job)return json(res,404,{detail:'Unknown published analysis'});
      if(path.startsWith('/agents/logs/'))return json(res,200,data.cases[job.payload.disease_id].logs);
      return json(res,200,jobRoute[2]?job.result.candidates:job);
    }
    const profile=path.match(/^\/(diseases|drugs)\/(.+)$/);
    if(profile&&method==='GET'){const entity=entities.find(e=>e.id===decodeURIComponent(profile[2])&&e.kind===(profile[1]==='drugs'?'Drug':'Disease'));return json(res,entity?200:404,entity||{detail:'Unknown entity'})}
    return json(res,404,{detail:'Endpoint unavailable in the published research snapshot'});
  }catch(error){if(error instanceof AccountError)return json(res,error.status,{detail:error.message});console.error('Atlas request failed:',error.name);return json(res,error instanceof SyntaxError?400:500,{detail:'Unable to process this request'})}
}
