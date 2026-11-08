"""Verify production authentication and published data without printing secrets."""
import json
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
BASE='https://atlas-drug-repurposing.vercel.app'

if __name__=='__main__':
    credentials=json.loads((ROOT/'runtime/cloud-auth/credentials.json').read_text(encoding='utf-8'))
    with httpx.Client(base_url=BASE,timeout=30) as client:
        index=client.get('/');print('Login page HTTP:',index.status_code,flush=True);index.raise_for_status()
        session=client.get('/api/auth/session');print('Session HTTP:',session.status_code,flush=True)
        assert session.status_code==200,session.text[:200]
        assert session.json()['configured'] and session.json()['user'] is None
        assert client.get('/api/graph/statistics').status_code==401
        failed=client.post('/api/auth/login',json={'username':'researcher','password':'intentionally-invalid-password'})
        assert failed.status_code==401
        response=client.post('/api/auth/login',json={'username':credentials['username'],'password':credentials['password']})
        print('Valid sign-in HTTP:',response.status_code,flush=True)
        assert response.status_code==200,response.text[:200]
        cookie=response.headers.get('set-cookie','')
        assert 'HttpOnly' in cookie and 'Secure' in cookie
        health=client.get('/api/health').json();assert health['published_snapshot']
        statistics=client.get('/api/graph/statistics').json();assert statistics['nodes']==1054
        diseases=client.get('/api/diseases').json();assert len(diseases)==3
        analyses=[]
        for disease in diseases:
            started=client.post('/api/predictions/run',json={'disease_id':disease['id']});started.raise_for_status()
            job=client.get('/api/predictions/'+started.json()['job_id']);job.raise_for_status()
            result=job.json();assert result['published_snapshot'] and result['result']['candidates']
            logs=client.get('/api/agents/logs/'+result['id']);logs.raise_for_status();assert len(logs.json())==9
            analyses.append({'disease':disease['name'],'returned_candidates':len(result['result']['candidates']),'recorded_stages':9})
        metrics=client.get('/api/models/metrics');metrics.raise_for_status()
        assert metrics.json()['graph_sha256']==statistics['sha256']
        assert client.post('/api/auth/logout').status_code==200
        assert client.get('/api/graph/statistics').status_code==401
        report={'url':BASE,'login_page':True,'valid_login':True,'invalid_login_rejected':True,'unauthenticated_api_rejected':True,
            'secure_session_cookie':True,'logout':True,'nodes':statistics['nodes'],'edges':statistics['edges'],
            'analyses':analyses,'edition':'Published real-source research snapshot; no hosted live Python training or local database connectivity.'}
        (ROOT/'runtime/vercel-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
