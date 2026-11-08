"""Conservative, traceable retrieval without automatic efficacy assertions."""
import asyncio
import httpx
from .connectors import EuropePMC,OpenFDA

class EvidenceService:
    def __init__(self,literature=None,safety=None):
        self.literature=literature or EuropePMC()
        self.safety=safety or OpenFDA()

    async def publications(self,drug:str,disease:str):
        """Keep metadata as search hits, not supportive or contradictory findings."""
        def term(value):return value.replace('"',' ').replace('\\',' ')
        query=f'TITLE_ABS:"{term(drug)}" AND TITLE_ABS:"{term(disease)}"'
        try:
            envelope=await asyncio.wait_for(self.literature.search(query),timeout=20)
            unique={}
            for record in envelope.payload['resultList']['result']:
                record_id=record.get('id');source=record.get('source')
                if not record_id or not source or not record.get('title'):continue
                key=record.get('doi') or f'{source}:{record_id}'
                unique[key]={'title':record['title'],'pmid':record_id if source=='MED' else None,'doi':record.get('doi'),'year':record.get('pubYear'),'url':f'https://europepmc.org/article/{source}/{record_id}','evidence_summary':'Retrieved search hit. Study design, findings, polarity and relevance have not been adjudicated.','evidence_type':'unreviewed_search_hit','source_record_id':f'{source}:{record_id}','retrieved_at':envelope.retrieved_at,'source_url':envelope.url}
            return {'status':'retrieved_unreviewed','publications':list(unique.values()),'source_url':envelope.url}
        except (httpx.HTTPError,ValueError,KeyError,TimeoutError) as exc:
            return {'status':'unavailable','publications':[],'error':type(exc).__name__}

    async def labels(self,drug:str):
        try:
            envelope=await asyncio.wait_for(self.safety.search(drug),timeout=20)
            records=[]
            for item in envelope.payload['results']:
                if not item.get('id'):continue
                records.append({'source':'openFDA drug labels','record_id':item['id'],'set_id':item.get('set_id'),'effective_time':item.get('effective_time'),'retrieved_at':envelope.retrieved_at,'source_url':envelope.url,'generic_names':item.get('openfda',{}).get('generic_name',[]),'sections':{k:item[k] for k in ['boxed_warning','warnings','warnings_and_cautions','adverse_reactions','contraindications','drug_interactions','clinical_pharmacology','pharmacokinetics'] if k in item},'interpretation':'Source label text; ingredient, formulation, recency and applicability require expert verification.'})
            return {'status':'retrieved_unreviewed','evidence':records,'data_gaps':['Label identity, formulation and applicability are not clinically adjudicated.'],'warnings':['Do not rely on openFDA data to make medical care decisions.','No safety inference from model score.']}
        except (httpx.HTTPError,ValueError,KeyError,TimeoutError) as exc:
            return {'status':'unavailable','evidence':[],'data_gaps':['No verified safety records available.'],'warnings':['No safety inference from model score.'],'error':type(exc).__name__}

    async def retrieve_candidates(self,candidates,disease_name,kind):
        semaphore=asyncio.Semaphore(2)
        async def one(candidate):
            async with semaphore:
                if kind=='literature':return candidate['drug_id'],await self.publications(candidate['drug_name'],disease_name)
                return candidate['drug_id'],await self.labels(candidate['drug_name'])
        return dict(await asyncio.gather(*(one(c) for c in candidates)))
