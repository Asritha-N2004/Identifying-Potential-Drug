"""Set Vercel secrets via stdin; never print credentials or place them in assets."""
import json
from pathlib import Path
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    credentials=json.loads((ROOT/'runtime/cloud-auth/credentials.json').read_text(encoding='utf-8'))
    package=ROOT/'runtime/vercel-cli/node_modules/vercel'
    metadata=json.loads((package/'package.json').read_text(encoding='utf-8'))
    cli=package/metadata['bin']['vercel']
    values={'LOGIN_USERNAME':credentials['username'],'LOGIN_PASSWORD_HASH':credentials['passwordHash'],'SESSION_SECRET':credentials['sessionSecret']}
    accounts=ROOT/'runtime/cloud-auth/accounts.json'
    if accounts.exists():
        users=json.loads(accounts.read_text(encoding='utf-8'))
        values['LOGIN_USERS_JSON']=json.dumps([{'username':user['username'],'passwordHash':user['passwordHash']} for user in users],separators=(',',':'))
    for key,value in values.items():
        args=[shutil.which('node'),str(cli),'env','add',key,'--environment','production,preview','--yes','--force','--scope','resum-projects','--cwd',str(ROOT/'runtime/atlas-vercel')]
        args.append('--no-sensitive' if key=='LOGIN_USERNAME' else '--sensitive')
        result=subprocess.run(args,input=value,capture_output=True,text=True)
        if result.returncode:
            message=result.stderr
            for secret in credentials.values():message=message.replace(secret,'[redacted]')
            message=message.replace(value,'[redacted]')
            raise SystemExit(message)
        print(key+': configured',flush=True)
