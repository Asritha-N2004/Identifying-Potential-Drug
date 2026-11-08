"""Exercise live app endpoints on the saved real-source snapshot."""
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app

if __name__=='__main__':
    manifest=json.loads((ROOT/'data/real/latest.json').read_text(encoding='utf-8'))
    os.environ['DATASET_PATH']=str(ROOT/'data/real'/manifest['snapshot_id']/'dataset.json')
    os.environ['MODEL_DIRECTORY']=str(ROOT/'models/real-checkpoints')
    os.environ['DATABASE_URL']='sqlite:///'+(ROOT/'runtime/real-api.db').as_posix()
    with TestClient(app) as client:
        def post(path,body=None):
            response=client.post(path,json=body) if body is not None else client.post(path)
            response.raise_for_status()
            return response.json()
        ingest=post('/api/data/ingest',{})
        job=client.get('/api/agents/status/'+ingest['job_id']).json()
        assert job['status']=='complete',job
        assert job['result']['snapshot_id']==manifest['snapshot_id']
        built=post('/api/graph/build',{'snapshot_id':manifest['snapshot_id']})
        assert built['trained_checkpoint']
        evaluation=post('/api/models/evaluate')
        diseases=client.get('/api/diseases/search').json()
        assert len(diseases)==3
        assert all(client.get('/api/diseases/'+d['id']+'/pathways').json() for d in diseases)
        report={'health':client.get('/api/health').json(),'graph':built['graph'],'evaluation':evaluation,
                'snapshot_id':manifest['snapshot_id'],'diseases':diseases,'checks':['ingest','graph build/activation','checkpoint reevaluation','three-disease search','disease pathways']}
        output=ROOT/'runtime/real-api-verification.json'
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'status':'passed','checks':report['checks'],'graph':built['graph']['sha256']},indent=2))
