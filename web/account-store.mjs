import {get,put} from '@vercel/blob';
import {hashPassword,hasConfiguredAccount} from './auth.mjs';

export class AccountError extends Error{constructor(status,message){super(message);this.status=status}}
const key='accounts/registry-v1.json';
export function createAccountStore(storage){
  const enabled=()=>storage.enabled();
  async function read(){
    if(!enabled())throw new AccountError(503,'Account creation is temporarily unavailable');
    try{
      const result=await storage.get(key,{access:'private',useCache:false});
      if(!result)return {accounts:{},etag:null};
      if(result.statusCode!==200)throw Error('Unexpected registry response');
      const data=await new Response(result.stream).json();
      if(!data.accounts||typeof data.accounts!=='object'||Array.isArray(data.accounts))throw Error('Invalid registry');
      return {accounts:data.accounts,etag:result.blob.etag};
    }catch(error){if(error instanceof AccountError)throw error;throw new AccountError(503,'Account storage is temporarily unavailable. Please try again.')}
  }
  return {
    enabled,
    async find(username){
      if(!enabled())return null;
      const {accounts}=await read();
      return Object.hasOwn(accounts,username)?accounts[username]:null;
    },
    async register(input){
      const username=typeof input.username==='string'?input.username.trim().toLowerCase():'';
      if(!/^[\p{L}\p{N}][\p{L}\p{M}\p{N} ._-]{0,31}$/u.test(username))throw new AccountError(422,'Please enter a name or nickname');
      if(typeof input.password!=='string'||input.password.length<12||input.password.length>200)throw new AccountError(422,'Use a password with 12–200 characters');
      if(input.password!==input.confirmPassword)throw new AccountError(422,'Passwords do not match');
      if(hasConfiguredAccount(username))throw new AccountError(409,'That username is already taken');
      if(!enabled())throw new AccountError(503,'Account creation is temporarily unavailable');
      const account={username,passwordHash:hashPassword(input.password),createdAt:new Date().toISOString()};
      for(let attempt=0;attempt<4;attempt++){
        const registry=await read();
        if(Object.hasOwn(registry.accounts,username))throw new AccountError(409,'That username is already taken');
        if(Object.keys(registry.accounts).length>=100)throw new AccountError(429,'Workspace account limit reached. Contact the administrator.');
        const next={accounts:{...registry.accounts,[username]:account},version:1};
        try{
          await storage.put(key,JSON.stringify(next),{access:'private',addRandomSuffix:false,contentType:'application/json',
            ...(registry.etag?{allowOverwrite:true,ifMatch:registry.etag}:{allowOverwrite:false})});
          return username;
        }catch(error){if(attempt===3)throw new AccountError(503,'Could not save your account. Please try again.')}
      }
    }
  };
}
export const accountStore=createAccountStore({get,put,enabled:()=>Boolean(process.env.BLOB_READ_WRITE_TOKEN)});
