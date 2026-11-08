"""Evidence must originate in supplied source responses, never generated claims."""
import asyncio
import httpx
from backend.app.connectors import EuropePMC,OpenFDA
from backend.app.evidence import EvidenceService

def test_retrieved_metadata_is_deduplicated_not_support(tmp_path):
    # Mocked metadata is a test fixture, never bundled as scientific evidence.
    transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'resultList':{'result':[{'id':'fixture-id','source':'MED','title':'MOCK publication metadata','doi':'fixture-doi'},{'id':'fixture-id','source':'MED','title':'MOCK publication metadata','doi':'fixture-doi'}]}}))
    service=EvidenceService(literature=EuropePMC(cache=tmp_path,transport=transport))
    result=asyncio.run(service.publications('test drug','test disease'))
    assert result['status']=='retrieved_unreviewed'
    assert len(result['publications'])==1
    assert result['publications'][0]['evidence_type']=='unreviewed_search_hit'

def test_safety_keeps_source_sections_and_gaps(tmp_path):
    transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'results':[{'id':'mock-label','openfda':{'generic_name':['TEST INGREDIENT']},'contraindications':['MOCK LABEL TEXT']}]}))
    service=EvidenceService(safety=OpenFDA(cache=tmp_path,transport=transport))
    result=asyncio.run(service.labels('test ingredient'))
    assert result['evidence'][0]['record_id']=='mock-label'
    assert result['data_gaps']
    assert 'contraindications' in result['evidence'][0]['sections']

def test_unavailable_safety_not_positive(tmp_path):
    transport=httpx.MockTransport(lambda r:httpx.Response(404,json={'error':'no records'}))
    result=asyncio.run(EvidenceService(safety=OpenFDA(cache=tmp_path,transport=transport)).labels('unknown'))
    assert result['status']=='unavailable' and result['evidence']==[]
