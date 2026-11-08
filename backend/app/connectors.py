"""Bounded public-source clients with cached, timestamped response envelopes.

Raw source metadata is not an assertion of efficacy or safety. Import requires
curated canonical mappings and edge provenance via the Dataset schema.
"""
import asyncio
import hashlib
import json
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
import httpx
from pydantic import BaseModel,Field

class SourceEnvelope(BaseModel):
    source: str
    url: str
    retrieved_at: str
    license: str
    payload: dict | list
    cached: bool=False

class RetrievalRequest(BaseModel):
    query: str=Field(min_length=1,max_length=300)
    page: int=Field(default=0,ge=0,le=100)

class SourceClient:
    source=''
    license='Source-specific terms; verify before redistribution'
    min_interval=.4
    def __init__(self,cache=Path('runtime/cache'),transport=None):
        self.cache=cache;self.transport=transport;self.last=0.0;self.lock=asyncio.Lock()

    async def request(self,url,params=None,body=None,refresh=False):
        key=hashlib.sha256(json.dumps([url,params,body],sort_keys=True).encode()).hexdigest()
        path=self.cache/f'{key}.json'
        if path.exists() and not refresh and time.time()-path.stat().st_mtime<86400:
            result=SourceEnvelope.model_validate_json(path.read_text(encoding='utf-8'));result.cached=True;return result
        async with self.lock:
            await asyncio.sleep(max(0,self.min_interval-(time.monotonic()-self.last)))
            async with httpx.AsyncClient(timeout=25,transport=self.transport,follow_redirects=False) as client:
                for attempt in range(4):
                    self.last=time.monotonic()
                    try:
                        response=await client.request('POST' if body else 'GET',url,params=params,json=body)
                        if response.status_code==429 or response.status_code>=500:
                            response.raise_for_status()
                        response.raise_for_status()
                        payload=response.json()
                        if not isinstance(payload,(dict,list)):raise ValueError('Expected JSON object or array')
                        if isinstance(payload,dict) and (payload.get('errors') or payload.get('error')):
                            raise ValueError('Source reported an API error')
                        result=SourceEnvelope(source=self.source,url=str(response.url),retrieved_at=datetime.now(timezone.utc).isoformat(),license=self.license,payload=payload)
                        self.cache.mkdir(parents=True,exist_ok=True)
                        temp=path.with_suffix('.tmp');temp.write_text(result.model_dump_json(),encoding='utf-8');temp.replace(path)
                        return result
                    except (httpx.TimeoutException,httpx.NetworkError,httpx.HTTPStatusError) as exc:
                        if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code<500 and exc.response.status_code!=429:raise
                        if attempt==3:raise
                        await asyncio.sleep(min(8,2**attempt))

class EuropePMC(SourceClient):
    source='Europe PMC'
    license='Metadata and article reuse terms vary; abstracts/full text retain publisher terms'
    async def search(self,query,page=0):
        result=await self.request('https://www.ebi.ac.uk/europepmc/webservices/rest/search',{'query':query,'format':'json','pageSize':25,'page':page+1,'resultType':'core'})
        if not isinstance(result.payload.get('resultList',{}).get('result'),list):raise ValueError('Invalid Europe PMC result schema')
        return result

class PubMed(SourceClient):
    source='PubMed'
    async def search(self,query,page=0):
        return await self.request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',{'db':'pubmed','term':query,'retmode':'json','retstart':page*25,'retmax':25})

class ChEMBL(SourceClient):
    source='ChEMBL';license='CC BY-SA 3.0; verify current source terms'
    async def search(self,query,page=0):
        return await self.request('https://www.ebi.ac.uk/chembl/api/data/molecule/search.json',{'q':query,'limit':25,'offset':page*25})

class PubChem(SourceClient):
    source='PubChem'
    async def search(self,query,page=0):
        if page:raise ValueError('Single compound lookup has no pagination')
        return await self.request(f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(query,safe="")}/property/MolecularFormula,MolecularWeight/JSON')

class UniProt(SourceClient):
    source='UniProt';license='CC BY 4.0; verify source release terms'
    async def search(self,query,page=0):
        if page:raise ValueError('Use UniProt cursor pagination via source Link metadata; only first page supported here')
        return await self.request('https://rest.uniprot.org/uniprotkb/search',{'query':query,'format':'json','size':25})

class Reactome(SourceClient):
    source='Reactome';license='CC0; verify current source terms'
    async def search(self,query,page=0):
        return await self.request('https://reactome.org/ContentService/search/query',{'query':query,'cluster':True,'Start row':page*25,'rows':25})

class STRING(SourceClient):
    source='STRING';license='CC BY 4.0; verify source release terms'
    min_interval=1.0
    async def search(self,query,page=0):
        if page:raise ValueError('STRING bounded interaction lookup has no pagination')
        return await self.request('https://string-db.org/api/json/network',{'identifiers':query,'species':9606,'limit':25,'caller_identity':'graph-repurposing-research'})

class OpenTargets(SourceClient):
    source='Open Targets';license='Mixed upstream terms; preserve upstream attribution'
    async def search(self,query,page=0):
        return await self.request('https://api.platform.opentargets.org/api/v4/graphql',body={'query':'query Search($q:String!,$page:Pagination!){search(queryString:$q,page:$page){hits{id name entity} total}}','variables':{'q':query,'page':{'index':page,'size':25}}})

class OpenFDA(SourceClient):
    """Retrieve label sections for review, never a patient suitability judgment."""
    source='openFDA drug labels'
    license='US government/openFDA terms; labeling content retains applicable third-party terms'
    async def search(self,query,page=0):
        # Quote a literal ingredient name; do not permit arbitrary query syntax.
        escaped=query.replace('\\','\\\\').replace('"','\\"')
        result=await self.request('https://api.fda.gov/drug/label.json',{'search':f'openfda.generic_name.exact:"{escaped}"','limit':5,'skip':page*5})
        if not isinstance(result.payload.get('results'),list):raise ValueError('Invalid openFDA label schema')
        return result

CLIENTS={'europe_pmc':EuropePMC,'pubmed':PubMed,'chembl':ChEMBL,'pubchem':PubChem,'uniprot':UniProt,'reactome':Reactome,'string':STRING,'opentargets':OpenTargets,'openfda':OpenFDA}
