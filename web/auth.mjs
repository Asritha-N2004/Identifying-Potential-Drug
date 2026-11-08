import {createHmac,randomBytes,scryptSync,timingSafeEqual} from 'node:crypto';

export const cookieName='__Host-atlas_session';
const ttl=8*60*60;
export function hashPassword(password,salt=randomBytes(16).toString('hex')){
  return `${salt}:${scryptSync(password,salt,64).toString('hex')}`;
}
export function verifyPassword(password,hash){
  if(typeof password!=='string'||password.length>200||!/^\w{32}:[a-f0-9]{128}$/.test(hash||''))return false;
  const [salt,expected]=hash.split(':');
  return timingSafeEqual(scryptSync(password,salt,64),Buffer.from(expected,'hex'));
}
function accounts(){
  const users=new Map();
  if(process.env.LOGIN_USERNAME&&process.env.LOGIN_PASSWORD_HASH)users.set(process.env.LOGIN_USERNAME,process.env.LOGIN_PASSWORD_HASH);
  if(process.env.LOGIN_USERS_JSON){
    const extra=JSON.parse(process.env.LOGIN_USERS_JSON);
    if(!Array.isArray(extra)||extra.length>100)throw Error('Invalid account configuration');
    for(const entry of extra){
      if(!entry||typeof entry.username!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$/.test(entry.username)||!/^\w{32}:[a-f0-9]{128}$/.test(entry.passwordHash||'')||users.has(entry.username))throw Error('Invalid account configuration');
      users.set(entry.username,entry.passwordHash);
    }
  }
  return users;
}
export function configured(){try{return Boolean(accounts().size&&process.env.SESSION_SECRET?.length>=32)}catch{return false}}
export function authenticateAccount(username,password){
  if(!configured())return false;
  const users=accounts();
  // Perform the same password work for unknown usernames.
  const valid=verifyPassword(password,users.get(username)||users.values().next().value);
  return users.has(username)&&valid;
}
export function hasConfiguredAccount(username){return accounts().has(username)}
export function issueSession(username,now=Math.floor(Date.now()/1000)){
  const payload=Buffer.from(JSON.stringify({sub:username,exp:now+ttl,nonce:randomBytes(16).toString('hex')})).toString('base64url');
  return payload+'.'+createHmac('sha256',process.env.SESSION_SECRET).update(payload).digest('base64url');
}
export function signedSessionUser(cookie,now=Math.floor(Date.now()/1000)){
  if(!configured()||typeof cookie!=='string'||cookie.length>8192)return null;
  const token=cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(cookieName+'='))?.slice(cookieName.length+1);
  if(!token)return null;
  const [payload,signature,...extra]=token.split('.');if(!payload||!signature||extra.length)return null;
  const expected=createHmac('sha256',process.env.SESSION_SECRET).update(payload).digest('base64url');
  const actual=Buffer.from(signature);const check=Buffer.from(expected);
  if(actual.length!==check.length||!timingSafeEqual(actual,check))return null;
  try{const data=JSON.parse(Buffer.from(payload,'base64url').toString());return data.exp>now&&typeof data.sub==='string'?data.sub:null}catch{return null}
}
export function readSession(cookie,now=Math.floor(Date.now()/1000)){const user=signedSessionUser(cookie,now);return user&&accounts().has(user)?user:null}
export function sessionCookie(value,logout=false){return `${cookieName}=${value}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${logout?0:ttl}`}
