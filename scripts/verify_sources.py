"""Opt-in live connector smoke checks; never run as part of offline tests."""
import asyncio,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.connectors import CLIENTS

QUERIES={'europe_pmc':'metformin','pubmed':'metformin','chembl':'metformin','pubchem':'metformin','uniprot':'gene:TP53 AND organism_id:9606','reactome':'apoptosis','string':'TP53','opentargets':'diabetes','openfda':'METFORMIN HYDROCHLORIDE'}

async def main():
    output=ROOT/'runtime/source-checks';output.mkdir(parents=True,exist_ok=True)
    async def check(name):
        try:
            result=await asyncio.wait_for(CLIENTS[name]().search(QUERIES[name]),timeout=45)
            path=output/f'{name}.json';path.write_text(result.model_dump_json(indent=2),encoding='utf-8')
            return name,{'status':'retrieved','url':result.url,'retrieved_at':result.retrieved_at,'cached':result.cached,'bytes':path.stat().st_size}
        except Exception as e:
            return name,{'status':'failed','error':type(e).__name__,'message':str(e)[:300]}
    results=dict(await asyncio.gather(*(check(name) for name in CLIENTS)))
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'results':results,'scope':'Connectivity and JSON envelope only; no scientific claim verification.'}
    (output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':asyncio.run(main())
