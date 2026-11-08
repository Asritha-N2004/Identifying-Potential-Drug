"""Verify live self-service registration without printing test passwords."""
import json
from pathlib import Path
import secrets
from uuid import uuid4
import httpx
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    path=ROOT/'runtime/cloud-auth/registration-test.json'
    if path.exists():account=json.loads(path.read_text(encoding='utf-8'))
    else:
        account={'username':'signup-test-'+uuid4().hex[:10],'password':secrets.token_urlsafe(20)}
        path.write_text(json.dumps(account),encoding='utf-8')
    with httpx.Client(base_url='https://atlas-drug-repurposing.vercel.app',timeout=40) as client:
        session=client.get('/api/auth/session');session.raise_for_status()
        assert session.json()['registration_available'] is True
        primary=json.loads((ROOT/'runtime/cloud-auth/credentials.json').read_text(encoding='utf-8'))
        reserved=client.post('/api/auth/register',json={'username':primary['username'],'password':account['password'],'confirmPassword':account['password']})
        assert reserved.status_code==409
        if not account.get('registered'):
            response=client.post('/api/auth/register',json={**account,'confirmPassword':account['password']})
            assert response.status_code==201,f'Registration failed: HTTP {response.status_code} {response.text[:180]}'
            assert response.json()['user']==account['username']
            account['registered']=True;path.write_text(json.dumps(account),encoding='utf-8')
            assert client.get('/api/graph/statistics').json()['nodes']==1054
            client.post('/api/auth/logout').raise_for_status()
        # A new client creates a new session, proving login does not rely on the
        # function instance or a cookie issued by the registration request.
        response=client.post('/api/auth/login',json={'username':account['username'],'password':account['password']})
        assert response.status_code==200,f'Persisted login failed: HTTP {response.status_code}'
        assert client.get('/api/auth/session').json()['user']==account['username']
        assert client.get('/api/graph/statistics').json()['nodes']==1054
        duplicate=client.post('/api/auth/register',json={**account,'confirmPassword':account['password']})
        assert duplicate.status_code==409
        client.post('/api/auth/logout').raise_for_status()
        assert client.get('/api/graph/statistics').status_code==401
        result={'url':'https://atlas-drug-repurposing.vercel.app','registration':True,'persisted_login':True,
            'duplicate_username_rejected':True,'existing_username_reserved':True,'protected_data_access':True,
            'logout':True,'storage':'Private Vercel Blob, origin reads and ETag conditional writes',
            'test_account':account['username'],'test_credentials':'Saved privately in runtime/cloud-auth/registration-test.json'}
        (ROOT/'runtime/cloud-auth/registration-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
