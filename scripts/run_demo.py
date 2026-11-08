"""Run reproducible training and discovery without external services."""
import asyncio,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.graph import KnowledgeGraph
from backend.app.ml import ModelService
from backend.app.storage import Store
from backend.app.agents import Orchestrator
from backend.app.schemas import PredictRequest

if __name__=='__main__':
    (ROOT/'runtime').mkdir(exist_ok=True)
    kg=KnowledgeGraph.load(ROOT/'data/sample/synthetic.json')
    model=ModelService(kg,ROOT/'models/checkpoints')
    if model.model is None:model.train()
    store=Store();store.seed(kg)
    job=str(uuid4());request=PredictRequest(disease_id='SYNTHETIC:Disease:0')
    store.create_job(job,'discovery',request.model_dump())
    asyncio.run(Orchestrator(kg,model,store).run(job,request))
    result=store.get(job)
    (ROOT/'runtime/demo-result.json').write_text(json.dumps(result,default=str,indent=2))
    print(json.dumps({'job_id':job,'status':result['status'],'candidates':len(result['result'].get('candidates',[]))}))
    if result['status']!='complete':raise SystemExit(result['error'])
