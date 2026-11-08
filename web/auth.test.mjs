import test from 'node:test';
import assert from 'node:assert/strict';
import {hashPassword,verifyPassword,issueSession,readSession,sessionCookie,authenticateAccount,configured} from './auth.mjs';
process.env.LOGIN_USERNAME='test-researcher';
process.env.SESSION_SECRET='test-only-secret-that-is-longer-than-thirty-two-characters';
process.env.LOGIN_PASSWORD_HASH=hashPassword('test-only-password');

test('passwords are hashed and wrong credentials fail',()=>{
  assert.ok(verifyPassword('test-only-password',process.env.LOGIN_PASSWORD_HASH));
  assert.equal(verifyPassword('incorrect',process.env.LOGIN_PASSWORD_HASH),false);
  assert.equal(verifyPassword('test-only-password','invalid-hash'),false);
});
test('signed sessions reject tampering and expiration',()=>{
  const token=issueSession('test-researcher',1000);
  assert.equal(readSession('__Host-atlas_session='+token,1001),'test-researcher');
  assert.equal(readSession('__Host-atlas_session='+token+'x',1001),null);
  assert.equal(readSession('__Host-atlas_session='+token,1000+9*3600),null);
  assert.equal(readSession('__Host-atlas_session=forged',1001),null);
  assert.match(sessionCookie(token),/HttpOnly; Secure; SameSite=Lax/);
  assert.match(sessionCookie('',true),/Max-Age=0/);
});

test('additional accounts preserve the original login and existing sessions',()=>{
  const original=issueSession('test-researcher');
  process.env.LOGIN_USERS_JSON=JSON.stringify([{username:'second-researcher',passwordHash:hashPassword('second-test-password')}]);
  try{
    assert.ok(authenticateAccount('test-researcher','test-only-password'));
    assert.ok(authenticateAccount('second-researcher','second-test-password'));
    assert.equal(authenticateAccount('second-researcher','test-only-password'),false);
    assert.equal(authenticateAccount('unknown-user','test-only-password'),false);
    assert.equal(readSession('__Host-atlas_session='+original),'test-researcher');
    assert.equal(readSession('__Host-atlas_session='+issueSession('second-researcher')),'second-researcher');
    process.env.LOGIN_USERS_JSON='[]';
    assert.equal(readSession('__Host-atlas_session='+issueSession('second-researcher')),null);
    process.env.LOGIN_USERS_JSON='malformed';assert.equal(configured(),false);
  }finally{delete process.env.LOGIN_USERS_JSON}
});

test('published API enforces authentication, CSRF checks and valid sign-in',async()=>{
  const {default:handler}=await import('../runtime/atlas-vercel/.vercel/output/functions/api/handler.func/handler.mjs');
  async function call(path,{method='GET',body,cookie,origin='https://atlas.test'}={}){
    let value;const headers={};
    const req={url:'/api'+path,method,body,headers:{host:'atlas.test',cookie,origin,'x-forwarded-for':'test-client'},socket:{remoteAddress:'test-client'}};
    const res={statusCode:200,setHeader:(key,v)=>{headers[key]=v},end:text=>{value=JSON.parse(text)}};
    await handler(req,res);return {status:res.statusCode,value,headers};
  }
  assert.equal((await call('/graph/statistics')).status,401);
  assert.equal((await call('/auth/login',{method:'POST',origin:'https://evil.test',body:{}})).status,403);
  assert.equal((await call('/auth/login',{method:'POST',body:{username:'test-researcher',password:'wrong'}})).status,401);
  const signed=await call('/auth/login',{method:'POST',body:{username:'test-researcher',password:'test-only-password'}});
  assert.equal(signed.status,200);const cookie=signed.headers['Set-Cookie'].split(';')[0];
  assert.equal((await call('/auth/session',{cookie})).value.user,'test-researcher');
  assert.equal((await call('/graph/statistics',{cookie})).value.nodes,1054);
  const opened=await call('/predictions/run',{method:'POST',cookie,body:{disease_id:'MONDO_0008383'}});
  assert.equal(opened.status,202);
  const result=await call('/predictions/'+opened.value.job_id,{cookie});
  assert.equal(result.value.published_snapshot,true);assert.equal(result.value.result.candidates.length,10);
  assert.equal((await call('/agents/logs/'+opened.value.job_id,{cookie})).value.length,9);
  assert.equal((await call('/models/train',{method:'POST',cookie,body:{epochs:8}})).status,409);
  assert.equal((await call('/auth/logout',{method:'POST',cookie})).headers['Set-Cookie'].includes('Max-Age=0'),true);
});
