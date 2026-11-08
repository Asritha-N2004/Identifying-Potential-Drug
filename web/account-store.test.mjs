import test from 'node:test';
import assert from 'node:assert/strict';
import {createAccountStore} from './account-store.mjs';
import {hashPassword,verifyPassword} from './auth.mjs';

function memory(){
  let data=null,version=0;
  return {enabled:()=>true,
    async get(){return data?{statusCode:200,stream:new Response(JSON.stringify(data)).body,blob:{etag:String(version)}}:null},
    async put(key,text,options){
      assert.equal(options.access,'private');
      if(data?options.ifMatch!==String(version):options.allowOverwrite!==false)throw Error('Concurrent write conflict');
      data=JSON.parse(text);version++;
    },snapshot:()=>data};
}
const input=username=>({username,password:'test-account-password',confirmPassword:'test-account-password'});
test('registration stores hashes, survives a new store instance and rejects duplicates',async()=>{
  const storage=memory();const store=createAccountStore(storage);
  assert.equal(await store.register(input('Test.User')),'test.user');
  const saved=await createAccountStore(storage).find('test.user');
  assert.ok(verifyPassword('test-account-password',saved.passwordHash));
  assert.equal(JSON.stringify(storage.snapshot()).includes('test-account-password'),false);
  await assert.rejects(()=>store.register(input('test.user')),error=>error.status===409);
});
test('simple names, short nicknames and spaces are accepted',async()=>{
  const store=createAccountStore(memory());
  assert.equal(await store.register(input('  Maya Reddy  ')),'maya reddy');
  assert.equal(await store.register(input('RK')),'rk');
  assert.equal(await store.register(input('A')),'a');
  assert.equal(await store.register(input('José')),'josé');
  await assert.rejects(()=>store.register(input('MAYA REDDY')),error=>error.status===409);
});
test('concurrent registrations preserve both users and reject a duplicate race',async()=>{
  const store=createAccountStore(memory());
  await Promise.all([store.register(input('account-one')),store.register(input('account-two'))]);
  assert.ok(await store.find('account-one'));assert.ok(await store.find('account-two'));
  const race=await Promise.allSettled([store.register(input('same-user')),store.register(input('same-user'))]);
  assert.equal(race.filter(r=>r.status==='fulfilled').length,1);
  assert.equal(race.find(r=>r.status==='rejected').reason.status,409);
});
test('registration validates passwords and protects configured accounts',async()=>{
  const store=createAccountStore(memory());
  await assert.rejects(()=>store.register(input('../bad')),error=>error.status===422);
  await assert.rejects(()=>store.register({...input('valid-user'),password:'short'}),error=>error.status===422);
  await assert.rejects(()=>store.register({...input('valid-user'),confirmPassword:'mismatch'}),error=>error.status===422);
  process.env.LOGIN_USERNAME='original-user';process.env.LOGIN_PASSWORD_HASH=hashPassword('original-password');
  try{await assert.rejects(()=>store.register(input('original-user')),error=>error.status===409)}finally{delete process.env.LOGIN_USERNAME;delete process.env.LOGIN_PASSWORD_HASH}
  await assert.rejects(()=>createAccountStore({...memory(),enabled:()=>false}).register(input('valid-user')),error=>error.status===503);
});
