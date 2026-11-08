// Add one private workspace account, preserving all existing credentials.
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {randomBytes} from 'node:crypto';
import {hashPassword} from '../web/auth.mjs';
const username=process.argv[2];
if(!username||!/^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$/.test(username))throw Error('Username must be 3–64 letters, numbers, dots, underscores or hyphens');
const directory=new URL('../runtime/cloud-auth/',import.meta.url);
const primary=JSON.parse(readFileSync(new URL('credentials.json',directory),'utf8'));
const file=new URL('accounts.json',directory);
const users=existsSync(file)?JSON.parse(readFileSync(file,'utf8')):[];
if(primary.username===username||users.some(user=>user.username===username))throw Error('That username already exists; existing accounts were preserved');
if(users.length>=100)throw Error('Account limit reached');
const password=randomBytes(18).toString('base64url');
users.push({username,password,passwordHash:hashPassword(password)});
writeFileSync(file,JSON.stringify(users,null,2));
writeFileSync(new URL(username+'-login.txt',directory),`Atlas dashboard\nURL: https://atlas-drug-repurposing.vercel.app\nUsername: ${username}\nPassword: ${password}\n\nKeep these login details private.\n`);
console.log(`Added ${username}. Private login details saved in runtime/cloud-auth/${username}-login.txt`);
