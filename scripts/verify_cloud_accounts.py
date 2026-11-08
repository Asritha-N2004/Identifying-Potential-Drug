"""Verify each configured account against production without printing passwords."""
import json
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    directory=ROOT/'runtime/cloud-auth'
    primary=json.loads((directory/'credentials.json').read_text(encoding='utf-8'))
    users=[primary]+json.loads((directory/'accounts.json').read_text(encoding='utf-8'))
    verified=[]
    for user in users:
        with httpx.Client(base_url='https://atlas-drug-repurposing.vercel.app',timeout=30) as client:
            response=client.post('/api/auth/login',json={'username':user['username'],'password':user['password']})
            assert response.status_code==200,f"Sign-in failed for {user['username']}: HTTP {response.status_code}"
            assert response.json()['user']==user['username']
            assert client.get('/api/auth/session').json()['user']==user['username']
            assert client.get('/api/graph/statistics').json()['nodes']==1054
            client.post('/api/auth/logout').raise_for_status()
            assert client.get('/api/graph/statistics').status_code==401
            verified.append(user['username'])
    report={'url':'https://atlas-drug-repurposing.vercel.app','verified_accounts':verified,'original_account_preserved':primary['username'] in verified,'passwords_printed':False}
    (ROOT/'runtime/cloud-auth/account-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
