// Create private deployment credentials without printing the password or secrets.
import {mkdirSync,existsSync,writeFileSync} from 'node:fs';
import {randomBytes} from 'node:crypto';
import {hashPassword} from '../web/auth.mjs';
const directory=new URL('../runtime/cloud-auth/',import.meta.url);
mkdirSync(directory,{recursive:true});
const file=new URL('credentials.json',directory);
if(!existsSync(file)){
  const password=randomBytes(18).toString('base64url');
  writeFileSync(file,JSON.stringify({username:'researcher',password,passwordHash:hashPassword(password),sessionSecret:randomBytes(48).toString('base64url')},null,2));
}
console.log('Private login credentials are ready in runtime/cloud-auth/credentials.json');
