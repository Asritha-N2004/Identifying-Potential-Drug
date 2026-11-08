"""Deterministic integration and scientific-integrity regression tests."""
import asyncio
from pathlib import Path
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app.graph import KnowledgeGraph
from backend.app.schemas import Dataset,PredictRequest
from backend.app.ml import ModelService
from backend.app.connectors import EuropePMC
from backend.app.main import app

ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture
def kg():return KnowledgeGraph.load(ROOT/'data/sample/synthetic.json')

def test_invalid_edge_rejected(kg):
    data=kg.dataset.model_dump(mode='json');data['relationships'][0]['target']='missing'
    with pytest.raises(ValidationError):Dataset.model_validate(data)

def test_no_fuzzy_merge(kg):
    assert kg.resolve('Synthetic Disease 01','Disease').id=='SYNTHETIC:Disease:0'
    with pytest.raises(ValueError):kg.resolve('Synthetic Disease','Disease')

def test_graph_provenance_and_paths(kg):
    assert kg.graph.number_of_nodes()==72
    paths=kg.paths('SYNTHETIC:Drug:0','SYNTHETIC:Disease:0')
    assert paths
    assert all(e['relation']!='TREATS' and e['provenance']['synthetic'] for p in paths for e in p['edges'])
    assert all(kg.graph.has_edge(e['source'],e['target']) for p in paths for e in p['edges'])

def test_weights():
    with pytest.raises(ValidationError):PredictRequest(disease_id='x',weights={'model':1})

def test_training_and_checkpoint(kg,tmp_path):
    service=ModelService(kg,tmp_path);report=service.train(epochs=8)
    assert 'TREATS' not in service.relations
    splits=[{(p['drug'],p['disease']) for p in report['split_pairs'][n]} for n in ['train','validation','test']]
    assert not splits[0]&splits[1] and not splits[0]&splits[2] and not splits[1]&splits[2]
    assert np.isfinite(report['metrics']['R-GCN']['roc_auc'])
    score=service.score('SYNTHETIC:Drug:0','SYNTHETIC:Disease:1')
    assert 0<=score<=1
    restored=ModelService(kg,tmp_path)
    assert restored.score('SYNTHETIC:Drug:0','SYNTHETIC:Disease:1')==pytest.approx(score)
    drug='SYNTHETIC:Drug:0';disease='SYNTHETIC:Disease:0'
    before=service.score(drug,disease)
    explanation=service.explain_edges(drug,disease,kg.paths(drug,disease),limit=3)
    assert explanation['edges'] and all(np.isfinite(e['score_difference']) for e in explanation['edges'])
    assert service.score(drug,disease)==pytest.approx(before)

def test_source_schema_cache_and_provenance(tmp_path):
    count=0
    def handler(request):
        nonlocal count
        count+=1
        return httpx.Response(200,json={'resultList':{'result':[{'id':'mock-source-record','title':'MOCK α‑synuclein ≥ β fixture'}]}})
    async def run():
        client=EuropePMC(cache=tmp_path,transport=httpx.MockTransport(handler))
        first=await client.search('query');second=await client.search('query')
        assert first.source=='Europe PMC' and first.retrieved_at
        assert second.cached
        assert second.payload['resultList']['result'][0]['title']=='MOCK α‑synuclein ≥ β fixture'
    asyncio.run(run());assert count==1

def test_source_invalid_payload(tmp_path):
    async def run():
        client=EuropePMC(cache=tmp_path,transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'bad':True})))
        with pytest.raises(ValueError):await client.search('query')
    asyncio.run(run())

def test_end_to_end_api(tmp_path,monkeypatch):
    monkeypatch.setenv('DATASET_PATH',str(ROOT/'data/sample/synthetic.json'))
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path.as_posix()}/test.db')
    monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path/'models'))
    monkeypatch.delenv('NEO4J_URI',raising=False)
    with TestClient(app) as client:
        assert client.get('/api/health').status_code==200
        assert len(client.get('/api/diseases').json())==8
        assert len(client.get('/api/diseases/search?offset=7&limit=2').json())==1
        assert client.get('/api/drugs/search?limit=-1').status_code==422
        trained=client.post('/api/model/train',json={'epochs':8}).json()
        assert client.get('/api/agents/status/'+trained['job_id']).json()['status']=='complete'
        response=client.post('/api/repurposing/predict',json={'disease_id':'SYNTHETIC:Disease:0'})
        assert response.status_code==202
        job=client.get('/api/repurposing/results/'+response.json()['job_id']).json()
        assert job['status']=='complete',job
        candidates=job['result']['candidates']
        prediction_id=response.json()['job_id']
        assert client.get('/api/predictions/'+prediction_id).json()['status']=='complete'
        assert client.get('/api/predictions/'+prediction_id+'/candidates').json()==candidates
        assert client.get('/api/predictions/'+prediction_id+'/explanations').json()==candidates
        assert client.get('/api/models/metrics').status_code==200
        evaluation=client.post('/api/models/evaluate')
        assert evaluation.status_code==200
        original=client.get('/api/models/metrics').json()['metrics']['R-GCN']
        assert evaluation.json()['metrics']['R-GCN']['roc_auc']==pytest.approx(original['roc_auc'])
        assert client.get('/api/graph/neighborhood/SYNTHETIC:Disease:0').status_code==200
        assert candidates and job['result']['quality']['passed']
        assert any(c['graph_paths'] and c['explanation']['model_sensitivity']['evaluated_edges']>0 for c in candidates)
        assert len(client.get('/api/agents/logs/'+job['id']).json())==9
        for c in candidates:
            assert c['synthetic'] and c['components']['literature']==0
            assert c['components']['pharmacology']==0
            assert c['publications']==[]
            assert not any(v=='SYNTHETIC:Disease:0' and d['relation']=='TREATS' for _,v,d in app.state.kg.graph.out_edges(c['drug_id'],data=True))
        assert client.post('/api/repurposing/predict',json={'disease_id':'missing'}).status_code==404
        assert client.get('/api/graph/subgraph/missing').status_code==404
        assert client.post('/api/model/train',json={'epochs':0}).status_code==422
