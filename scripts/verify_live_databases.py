"""Exercise a real HTTP server with both databases and the real-source graph."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime/integration-python'))
from scripts.run_database_tests import configure


if __name__=='__main__':
    credentials=configure()
    import httpx
    from sqlalchemy import select,func
    from backend.app.storage import Store,EntityRecord,RelationshipRecord
    from backend.app.graph import KnowledgeGraph
    from backend.app.neo4j_store import Neo4jStore
    manifest=json.loads((ROOT/'data/real/latest.json').read_text(encoding='utf-8'))
    dataset=ROOT/'data/real'/manifest['snapshot_id']/'dataset.json'
    kg=KnowledgeGraph.load(dataset)
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',18000))==0:raise SystemExit('Port 18000 already in use; refusing to reuse unknown server')
    env=os.environ.copy()
    env.update({'PYTHONPATH':str(ROOT/'runtime/integration-python')+os.pathsep+str(ROOT),
        'DATABASE_URL':os.environ['TEST_POSTGRES_URL'],'NEO4J_URI':os.environ['TEST_NEO4J_URI'],
        'NEO4J_USERNAME':'neo4j','NEO4J_PASSWORD':credentials['neo4j_password'],
        'DATASET_PATH':str(dataset),'MODEL_DIRECTORY':str(ROOT/'models/real-checkpoints'),
        'ADMIN_API_KEY':secrets.token_urlsafe(24)})
    headers={'X-API-Key':env['ADMIN_API_KEY']}
    output=ROOT/'runtime/database-tests';output.mkdir(exist_ok=True)
    with (output/'live-server.log').open('ab') as log, httpx.Client(base_url='http://127.0.0.1:18000',timeout=30) as client:
        def start():
            process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','18000'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            for _ in range(120):
                if process.poll() is not None:raise RuntimeError('Server exited; inspect live-server.log')
                try:
                    response=client.get('/api/health',timeout=1)
                    if response.status_code==200:return process,response.json()
                except httpx.HTTPError:pass
                time.sleep(.5)
            process.terminate();process.wait(timeout=15)
            raise RuntimeError('Server startup timed out')
        def stop(process):
            process.terminate();process.wait(timeout=20)
        process=None
        try:
            process,health=start()
            assert health['database']=='postgresql' and health['neo4j'] and health['trained_checkpoint']
            assert client.get('/').status_code==200
            statistics=client.get('/api/graph/statistics').json()
            assert statistics['sha256']==kg.digest
            evaluation=client.post('/api/models/evaluate',headers=headers);evaluation.raise_for_status()
            requested=client.post('/api/predictions/run',json={'disease_id':'MONDO_0008383'},headers=headers)
            requested.raise_for_status();job_id=requested.json()['job_id']
            for _ in range(360):
                job=client.get('/api/predictions/'+job_id).json()
                if job['status'] in {'complete','failed'}:break
                time.sleep(.5)
            assert job['status']=='complete',job.get('error')
            executions=client.get('/api/agents/logs/'+job_id).json();assert len(executions)==9
            print('Real HTTP workflow complete; verifying persistence after server restart...',flush=True)
            stop(process);process=None
            process,restarted=start()
            assert client.get('/api/predictions/'+job_id).json()['status']=='complete'
            assert restarted['trained_checkpoint']
            sql=Store(env['DATABASE_URL'])
            try:
                with sql.session() as session:
                    nodes=session.scalar(select(func.count()).select_from(EntityRecord).where(EntityRecord.id.in_(kg.entities)))
                    assert nodes==len(kg.entities)
                assert sql.get(job_id)['status']=='complete'
            finally:sql.engine.dispose()
            neo=Neo4jStore(env['NEO4J_URI'],'neo4j',credentials['neo4j_password'])
            try:
                with neo.driver.session() as session:
                    nodes=session.run('MATCH (n:Entity) WHERE n.id IN $ids RETURN count(n) AS n',ids=list(kg.entities)).single()['n']
                    edges=session.run('MATCH (a:Entity)-[r:BIOMEDICAL]->(b:Entity) WHERE a.id IN $ids AND b.id IN $ids RETURN count(r) AS n',ids=list(kg.entities)).single()['n']
                    assert nodes==len(kg.entities) and edges==kg.graph.number_of_edges()
            finally:neo.close()
            result={'status':'passed','server':'Uvicorn on localhost:18000 (stopped after verification)',
                'database':'PostgreSQL','neo4j':True,'graph_sha256':kg.digest,'nodes':nodes,'edges':edges,
                'disease':'MONDO_0008383','candidates':len(job['result']['candidates']),'agent_stages':len(executions),
                'evaluation':evaluation.json()['metrics'],'restart_persistence':True,
                'deployment':'Native Windows processes; not Docker containers'}
            (output/'live-http.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result,indent=2))
        finally:
            if process is not None and process.poll() is None:stop(process)
