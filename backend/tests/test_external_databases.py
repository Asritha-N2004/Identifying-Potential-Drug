"""Opt-in live integration; each test owns a unique synthetic namespace."""
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
from backend.app.graph import KnowledgeGraph

ROOT=Path(__file__).resolve().parents[2]
PG=bool(os.getenv('TEST_POSTGRES_URL'))
NEO=bool(os.getenv('TEST_NEO4J_URI'))


def neo_password():
    return os.getenv('TEST_NEO4J_PASSWORD') or os.environ['NEO4J_PASSWORD']


@pytest.fixture
def isolated_graph():
    dataset=KnowledgeGraph.load(ROOT/'data/sample/synthetic.json').dataset.model_copy(deep=True)
    prefix='SYNTHETIC:INTEGRATION:'+uuid4().hex+':'
    ids={e.id:prefix+e.id.removeprefix('SYNTHETIC:') for e in dataset.entities}
    for entity in dataset.entities:
        entity.id=ids[entity.id]
        entity.name='Integration α β '+entity.name
    for edge in dataset.relationships:
        edge.source=ids[edge.source];edge.target=ids[edge.target]
    return KnowledgeGraph(dataset),prefix


def cleanup_postgres(store,prefix,jobs=()):
    from sqlalchemy import delete
    from backend.app.storage import AgentExecution,Job,EntityRecord,RelationshipRecord
    with store.session.begin() as session:
        if jobs:
            session.execute(delete(AgentExecution).where(AgentExecution.job_id.in_(jobs)))
            session.execute(delete(Job).where(Job.id.in_(jobs)))
        session.execute(delete(RelationshipRecord).where(RelationshipRecord.source_id.startswith(prefix)))
        session.execute(delete(EntityRecord).where(EntityRecord.id.startswith(prefix)))


@pytest.mark.skipif(not NEO,reason='TEST_NEO4J_URI not configured')
def test_actual_neo4j(isolated_graph):
    from backend.app.neo4j_store import Neo4jStore
    kg,prefix=isolated_graph
    store=Neo4jStore(os.environ['TEST_NEO4J_URI'],os.getenv('TEST_NEO4J_USERNAME','neo4j'),neo_password())
    try:
        store.sync(kg);store.sync(kg)
        with store.driver.session() as session:
            assert session.run('MATCH (e:Entity) WHERE e.id STARTS WITH $prefix RETURN count(e) AS n',prefix=prefix).single()['n']==len(kg.entities)
            edges=list(session.run('MATCH (a:Entity)-[r:BIOMEDICAL]->(b:Entity) WHERE a.id STARTS WITH $prefix RETURN a.id AS source,b.id AS target,r.relation AS relation,r.json AS json',prefix=prefix))
            assert len(edges)==len(kg.dataset.relationships)
            for record in edges:
                payload=json.loads(record['json'])
                assert payload['source']==record['source'] and payload['target']==record['target']
                assert payload['relation']==record['relation']
                assert payload['provenance']['synthetic'] is True
                assert payload['provenance']['reference']
            sample=next(iter(kg.entities.values()))
            stored=session.run('MATCH (e:Entity {id:$id}) RETURN e.json AS json',id=sample.id).single()
            assert json.loads(stored['json'])==sample.model_dump()
    finally:
        with store.driver.session() as session:
            session.run('MATCH (e:Entity) WHERE e.id STARTS WITH $prefix DETACH DELETE e',prefix=prefix).consume()
        store.close()


@pytest.mark.skipif(not PG,reason='TEST_POSTGRES_URL not configured')
def test_actual_postgres(isolated_graph):
    from sqlalchemy import select,func
    from backend.app.storage import Store,EntityRecord,RelationshipRecord
    kg,prefix=isolated_graph
    store=Store(os.environ['TEST_POSTGRES_URL']);job=str(uuid4())
    try:
        store.seed(kg);store.seed(kg)
        with store.session() as session:
            assert session.scalar(select(func.count()).select_from(EntityRecord).where(EntityRecord.id.startswith(prefix)))==len(kg.entities)
            assert session.scalar(select(func.count()).select_from(RelationshipRecord).where(RelationshipRecord.source_id.startswith(prefix)))==len(kg.dataset.relationships)
            sample=next(iter(kg.entities.values()))
            assert session.get(EntityRecord,sample.id).data==sample.model_dump()
        store.create_job(job,'integration',{'unicode':'α β'})
        store.log(job,'live database roundtrip',.1,{'provenance_preserved':True})
        store.update(job,status='complete',result={'verified':True})
        other=Store(os.environ['TEST_POSTGRES_URL'])
        try:
            assert other.get(job)['status']=='complete'
            assert other.get(job)['payload']=={'unicode':'α β'}
            assert other.logs(job)[0]['output_summary']['provenance_preserved']
        finally:other.engine.dispose()
    finally:
        cleanup_postgres(store,prefix,[job]);store.engine.dispose()


@pytest.mark.skipif(not (PG and NEO),reason='Both live database URLs required')
def test_app_with_live_databases(isolated_graph,tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.storage import Store
    from backend.app.neo4j_store import Neo4jStore
    kg,prefix=isolated_graph
    path=tmp_path/'graph.json';path.write_text(kg.dataset.model_dump_json(),encoding='utf-8')
    monkeypatch.setenv('DATASET_PATH',str(path))
    monkeypatch.setenv('DATABASE_URL',os.environ['TEST_POSTGRES_URL'])
    monkeypatch.setenv('NEO4J_URI',os.environ['TEST_NEO4J_URI'])
    monkeypatch.setenv('NEO4J_USERNAME',os.getenv('TEST_NEO4J_USERNAME','neo4j'))
    monkeypatch.setenv('NEO4J_PASSWORD',neo_password())
    monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path/'models'))
    monkeypatch.delenv('ADMIN_API_KEY',raising=False)
    jobs=[]
    try:
        with TestClient(app) as client:
            health=client.get('/api/health').json()
            assert health['database']=='postgresql' and health['neo4j'] is True
            train=client.post('/api/models/train',json={'epochs':8}).json();jobs.append(train['job_id'])
            assert client.get('/api/agents/status/'+train['job_id']).json()['status']=='complete'
            disease=next(e.id for e in kg.entities.values() if e.kind=='Disease')
            predicted=client.post('/api/predictions/run',json={'disease_id':disease}).json();jobs.append(predicted['job_id'])
            result=client.get('/api/predictions/'+predicted['job_id']).json()
            assert result['status']=='complete',result
            assert result['result']['candidates']
            assert len(client.get('/api/agents/logs/'+predicted['job_id']).json())==9
        with TestClient(app) as client:
            assert client.get('/api/predictions/'+predicted['job_id']).json()['status']=='complete'
            assert client.get('/api/health').json()['trained_checkpoint'] is True
    finally:
        store=Store(os.environ['TEST_POSTGRES_URL'])
        cleanup_postgres(store,prefix,jobs);store.engine.dispose()
        neo=Neo4jStore(os.environ['TEST_NEO4J_URI'],os.getenv('TEST_NEO4J_USERNAME','neo4j'),neo_password())
        with neo.driver.session() as session:
            session.run('MATCH (e:Entity) WHERE e.id STARTS WITH $prefix DETACH DELETE e',prefix=prefix).consume()
        neo.close()
