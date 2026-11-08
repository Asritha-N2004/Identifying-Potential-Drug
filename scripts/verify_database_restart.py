"""Verify stored records survive restarts of only our workspace test servers."""
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime/integration-python'))
from scripts.run_database_tests import configure

if __name__=='__main__':
    credentials=configure()
    import os
    from backend.app.storage import Store,Job
    from neo4j import GraphDatabase
    job_id=str(uuid4());node_id='SYNTHETIC:RESTART:'+job_id
    url=os.environ['TEST_POSTGRES_URL'];uri=os.environ['TEST_NEO4J_URI']
    store=Store(url)
    store.create_job(job_id,'restart-probe',{'purpose':'synthetic persistence check'})
    store.update(job_id,status='complete',result={'persisted':True});store.engine.dispose()
    with GraphDatabase.driver(uri,auth=('neo4j',credentials['neo4j_password'])) as driver:
        with driver.session() as session:
            session.run('CREATE (n:Entity {id:$id, kind:"PersistenceTest", name:"Synthetic restart probe"})',id=node_id).consume()
    for action in ['stop','start']:
        print('Local database lifecycle: '+action,flush=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/local_databases.py'),action],check=True)
    store=Store(url)
    try:
        assert store.get(job_id)['result']=={'persisted':True}
        with GraphDatabase.driver(uri,auth=('neo4j',credentials['neo4j_password'])) as driver:
            with driver.session() as session:
                assert session.run('MATCH (n:Entity {id:$id}) RETURN n.name AS name',id=node_id).single()['name']=='Synthetic restart probe'
                session.run('MATCH (n:Entity {id:$id}) DELETE n',id=node_id).consume()
        result={'status':'passed','postgres_record_survived_restart':True,'neo4j_record_survived_restart':True,
                'scope':'Workspace-only local servers, loopback ports 55432/17687; no data directories removed.',
                'neo4j_stop':'Owned console process tree terminated; transaction log recovery on restart.'}
        output=ROOT/'runtime/database-tests/database-restart.json'
        output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        with store.session.begin() as session:
            record=session.get(Job,job_id)
            if record:session.delete(record)
        store.engine.dispose()
