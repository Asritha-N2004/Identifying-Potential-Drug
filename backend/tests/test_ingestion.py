"""Mock source records test ETL behavior; these are not biomedical evidence."""
import asyncio
import hashlib
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app.connectors import OpenTargets, EuropePMC, SourceEnvelope
from backend.app.ingestion import BiomedicalIngestor
from backend.app.graph import KnowledgeGraph
from backend.app.main import app

ROOT=Path(__file__).resolve().parents[2]


def responses(request):
    if request.method=='GET':
        return httpx.Response(200,json={'resultList':{'result':[]}})
    variables=json.loads(request.content)['variables']
    target={'id':'MOCK_GENE','approvedSymbol':'MOCK','proteinIds':[], 'pathways':[{'pathwayId':'MOCK_PATH','pathway':'Mock pathway'}]}
    if variables['id'].startswith('MONDO'):
        disease={'id':variables['id'],'name':'Mock disease','associatedTargets':{'count':1,'rows':[
            {'target':target,'score':.99,'datatypeScores':[{'id':'genetic_association','score':.6}], 'datasourceScores':[]}]},
            'drugAndClinicalCandidates':{'count':1,'rows':[{'id':'mock-indication','maxClinicalStage':'APPROVAL','drug':{'id':'MOCK_DRUG','name':'Mock drug'}}]}}
        return httpx.Response(200,json={'data':{'disease':disease}})
    return httpx.Response(200,json={'data':{'drug':{'id':'MOCK_DRUG','name':'Mock drug','maximumClinicalStage':'APPROVAL',
        'mechanismsOfAction':{'rows':[{'actionType':'INHIBITOR','mechanismOfAction':'Mock mechanism','targets':[target]}]}}}})


def make_ingestor(tmp_path):
    transport=httpx.MockTransport(responses)
    return BiomedicalIngestor(tmp_path/'data/real',OpenTargets(tmp_path/'cache',transport),EuropePMC(tmp_path/'cache',transport))


def test_ingestion_roundtrip_and_no_aggregate_score(tmp_path):
    ingestor=make_ingestor(tmp_path)
    manifest=asyncio.run(ingestor.acquire(['MONDO_1234567'],10,1))
    directory=tmp_path/'data/real'/manifest['snapshot_id']
    raw=json.loads((directory/'raw.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()==manifest['snapshot_id']
    kg=KnowledgeGraph.load(directory/'dataset.json')
    associations=[d for _,_,d in kg.graph.edges(data=True) if d['relation']=='ASSOCIATED_WITH']
    assert associations[0]['provenance']['confidence']==.6
    assert not kg.analysis_graph().has_edge('MOCK_DRUG','MONDO_1234567')
    assert manifest['selected_drugs']==1
    # Repeating cached acquisition yields the identical snapshot.
    second=asyncio.run(make_ingestor(tmp_path).acquire(['MONDO_1234567'],10,1))
    assert second['entities']==manifest['entities']
    assert second['snapshot_id']==manifest['snapshot_id']


def test_known_drug_only_association_is_dropped():
    request=httpx.Request('POST','https://example.invalid',json={'variables':{'id':'MONDO_1234567'}})
    payload=responses(request).json()
    payload['data']['disease']['associatedTargets']['rows'][0]['datatypeScores']=[{'id':'known_drug','score':1}]
    envelope=SourceEnvelope(source='Mock',url='https://example.invalid',retrieved_at='2026-01-01T00:00:00Z',license='test-only',payload=payload)
    dataset,_=BiomedicalIngestor.normalize([envelope],set())
    assert not dataset.relationships


def test_missing_endpoints_and_graph_promotion(tmp_path,monkeypatch):
    import backend.app.main as main
    manifest=asyncio.run(make_ingestor(tmp_path).acquire(['MONDO_1234567'],10,1))
    monkeypatch.setattr(main,'ROOT',tmp_path)
    monkeypatch.setenv('DATASET_PATH',str(ROOT/'data/sample/synthetic.json'))
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path.as_posix()}/test.db')
    monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path/'models'))
    monkeypatch.delenv('NEO4J_URI',raising=False)
    async def acquire_mock(*args,**kwargs):return manifest
    monkeypatch.setattr(BiomedicalIngestor,'acquire',acquire_mock)
    with TestClient(app) as client:
        ingestion=client.post('/api/data/ingest',json={'disease_ids':['MONDO_1234567']})
        assert ingestion.status_code==202
        assert client.get('/api/agents/status/'+ingestion.json()['job_id']).json()['result']['snapshot_id']==manifest['snapshot_id']
        assert client.post('/api/models/evaluate').status_code==409
        assert client.post('/api/graph/build',json={'snapshot_id':'../escape'}).status_code==422
        assert client.post('/api/data/ingest',json={'disease_ids':['invalid']} ).status_code==422
        assert client.post('/api/graph/build',json={'snapshot_id':'f'*64}).status_code==404
        before=client.get('/api/graph/statistics').json()['sha256']
        directory=tmp_path/'data/real'/manifest['snapshot_id']
        original=(directory/'raw.json').read_text(encoding='utf-8')
        (directory/'raw.json').write_text('[]',encoding='utf-8')
        assert client.post('/api/graph/build',json={'snapshot_id':manifest['snapshot_id']}).status_code==422
        assert client.get('/api/graph/statistics').json()['sha256']==before
        (directory/'raw.json').write_text(original,encoding='utf-8')
        result=client.post('/api/graph/build',json={'snapshot_id':manifest['snapshot_id']})
        assert result.status_code==200,result.text
        assert result.json()['trained_checkpoint'] is False
        assert client.get('/api/diseases').json()[0]['name']=='Mock disease'


def test_ingestion_failure_preserves_active_graph(tmp_path,monkeypatch):
    monkeypatch.setenv('DATASET_PATH',str(ROOT/'data/sample/synthetic.json'))
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path.as_posix()}/test.db')
    monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path/'models'))
    monkeypatch.delenv('NEO4J_URI',raising=False)
    async def unavailable(*args,**kwargs):raise httpx.ConnectError('mock outage')
    monkeypatch.setattr(BiomedicalIngestor,'acquire',unavailable)
    with TestClient(app) as client:
        before=client.get('/api/graph/statistics').json()['sha256']
        response=client.post('/api/data/ingest',json={})
        assert response.status_code==202
        job=client.get('/api/agents/status/'+response.json()['job_id']).json()
        assert job['status']=='failed'
        assert client.get('/api/graph/statistics').json()['sha256']==before
