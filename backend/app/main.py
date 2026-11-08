"""FastAPI research service. Start from repository root with uvicorn."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import FastAPI,HTTPException,BackgroundTasks,Request,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .schemas import PredictRequest,TrainRequest,IngestRequest,BuildRequest
from .graph import KnowledgeGraph
from .ml import ModelService
from .storage import Store
from .agents import Orchestrator
from .connectors import CLIENTS,RetrievalRequest

ROOT=Path(__file__).resolve().parents[2]
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger('research')

@asynccontextmanager
async def lifespan(app):
    (ROOT/'runtime').mkdir(parents=True,exist_ok=True)
    import json
    active=ROOT/'runtime/active-dataset.json'
    dataset_path=ROOT/'data/sample/synthetic.json'
    if active.exists():
        from .schemas import BuildRequest
        selected=BuildRequest.model_validate(json.loads(active.read_text(encoding='utf-8')))
        dataset_path=ROOT/'data/real'/selected.snapshot_id/'dataset.json'
    kg=KnowledgeGraph.load(Path(os.getenv('DATASET_PATH',dataset_path)))
    store=Store();store.seed(kg)
    # An interrupted process is never reported as still executing after restart.
    from sqlalchemy import update
    from .storage import Job
    with store.session.begin() as session:
        session.execute(update(Job).where(Job.status.in_(['running','queued'])).values(status='failed',error='Process restarted; rerun this job.'))
    app.state.kg=kg;app.state.store=store
    app.state.model=ModelService(kg,Path(os.getenv('MODEL_DIRECTORY',ROOT/'models/checkpoints')))
    app.state.model_lock=asyncio.Lock()
    app.state.ingest_lock=asyncio.Lock()
    app.state.orchestrator=Orchestrator(kg,app.state.model,store)
    app.state.clients={name:cls() for name,cls in CLIENTS.items()}
    neo=None
    if os.getenv('NEO4J_URI'):
        from .neo4j_store import Neo4jStore
        if not os.getenv('NEO4J_PASSWORD'):raise ValueError('NEO4J_PASSWORD required when NEO4J_URI is set')
        neo=Neo4jStore(os.environ['NEO4J_URI'],os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD'])
        neo.sync(kg)
    app.state.neo4j=bool(neo)
    app.state.neo4j_store=neo
    yield
    if neo:neo.close()
    store.engine.dispose()

app=FastAPI(title='Graph-based Drug Repurposing Research',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('FRONTEND_URL','http://localhost:5173')],allow_methods=['GET','POST'],allow_headers=['Content-Type','X-API-Key'])

@app.middleware('http')
async def audit(request: Request,call_next):
    if request.method=='POST' and os.getenv('ADMIN_API_KEY') and request.headers.get('X-API-Key')!=os.environ['ADMIN_API_KEY']:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401,content={'detail':'API key required'})
    response=await call_next(request)
    logger.info('request method=%s path=%s status=%s',request.method,request.url.path,response.status_code)
    return response

def entity(id,kind=None):
    e=app.state.kg.entities.get(id)
    if e is None or kind and e.kind!=kind:raise HTTPException(404,'Unknown entity')
    return e

@app.get('/api/health')
def health():
    return {'status':'ok','mode':'synthetic' if app.state.kg.statistics()['synthetic'] else 'curated','database':app.state.store.engine.dialect.name,'neo4j':app.state.neo4j,'trained_checkpoint':app.state.model.model is not None}

@app.get('/api/diseases')
@app.get('/api/diseases/search')
def diseases(q: str=Query(default='',max_length=300),limit:int=Query(default=100,ge=1,le=100),offset:int=Query(default=0,ge=0)):
    return [e.model_dump() for e in app.state.kg.entities.values() if e.kind=='Disease' and q.casefold() in (e.name+' '+e.id+' '+' '.join(e.synonyms)).casefold()][offset:offset+limit]

@app.get('/api/drugs')
@app.get('/api/drugs/search')
def drugs(q: str=Query(default='',max_length=300),limit:int=Query(default=100,ge=1,le=100),offset:int=Query(default=0,ge=0)):
    return [e.model_dump() for e in app.state.kg.entities.values() if e.kind=='Drug' and q.casefold() in (e.name+' '+e.id+' '+' '.join(e.synonyms)).casefold()][offset:offset+limit]

@app.get('/api/diseases/{id}')
def disease_detail(id: str):return entity(id,'Disease')

@app.get('/api/drugs/{id}')
def drug_detail(id: str):return entity(id,'Drug')

def related(id,kind):
    entity(id)
    graph=app.state.kg.subgraph(id)
    return [n for n in graph['nodes'] if n['kind']==kind]

@app.get('/api/diseases/{id}/genes')
def genes(id:str):return related(id,'Gene')

@app.get('/api/diseases/{id}/pathways')
def pathways(id:str):
    entity(id,'Disease')
    g=app.state.kg.analysis_graph()
    genes={n for n in g[id] if app.state.kg.entities[n].kind=='Gene'}
    ids={n for gene in genes for n in g[gene] if app.state.kg.entities[n].kind=='Pathway'}
    return [app.state.kg.entities[n].model_dump() for n in sorted(ids)]

@app.get('/api/drugs/{id}/targets')
def targets(id:str):
    entity(id,'Drug')
    ids={v for _,v,d in app.state.kg.graph.out_edges(id,data=True) if d['relation'] in {'TARGETS','INHIBITS','ACTIVATES'}}
    return [app.state.kg.entities[n].model_dump() for n in sorted(ids)]

@app.get('/api/graph/statistics')
def statistics():return app.state.kg.statistics()

@app.get('/api/graph/paths')
@app.get('/api/graph/path')
def paths(source:str,target:str):
    entity(source);entity(target)
    return app.state.kg.paths(source,target)

@app.get('/api/graph/neighbors/{id}')
@app.get('/api/graph/neighborhood/{id}')
@app.get('/api/graph/subgraph/{id}')
def subgraph(id:str):
    entity(id)
    return app.state.kg.subgraph(id)

async def discover(job,request):
    async with app.state.model_lock:
        await app.state.orchestrator.run(job,request)

@app.post('/api/repurposing/predict',status_code=202)
@app.post('/api/predictions/run',status_code=202)
@app.post('/api/repurposing/rank',status_code=202)
@app.post('/api/agents/run',status_code=202)
def predict(request:PredictRequest,background:BackgroundTasks):
    try: resolved=app.state.kg.resolve(request.disease_id,'Disease')
    except ValueError as e:raise HTTPException(404,str(e))
    if app.state.model.model is None:raise HTTPException(409,'Train a checkpoint first using POST /api/model/train')
    request=request.model_copy(update={'disease_id':resolved.id})
    id=str(uuid4());app.state.store.create_job(id,'discovery',request.model_dump())
    background.add_task(discover,id,request)
    return {'job_id':id,'status':'queued'}

@app.get('/api/repurposing/results/{id}')
@app.get('/api/predictions/{id}')
@app.get('/api/agents/status/{id}')
def result(id:str):
    job=app.state.store.get(id)
    if job is None:raise HTTPException(404,'Unknown job')
    return job

@app.get('/api/agents/logs/{id}')
def logs(id:str):
    result(id)
    return app.state.store.logs(id)

@app.get('/api/predictions/{id}/candidates')
def prediction_candidates(id:str):
    job=result(id)
    if job['kind']!='discovery':raise HTTPException(422,'Not a discovery job')
    if job['status']!='complete':raise HTTPException(409,'Discovery has not completed')
    return job['result']['candidates']

@app.get('/api/predictions/{id}/explanations')
def prediction_explanations(id:str):
    # Full candidates retain path evidence, components and limitations together.
    return prediction_candidates(id)

@app.get('/api/repurposing/candidates/{id}')
def candidates(id:str):
    from sqlalchemy import select
    from .storage import Job
    entity(id,'Disease')
    with app.state.store.session() as s:
        jobs=s.scalars(select(Job).where(Job.kind=='discovery',Job.status=='complete').order_by(Job.created_at.desc()))
        for job in jobs:
            if job.payload['disease_id']==id:return job.result
    raise HTTPException(404,'No completed discovery for this disease')

@app.get('/api/model/info')
def info():
    return {'name':'R-GCN + DistMult','trained':app.state.model.model is not None,'graph_sha256':app.state.kg.digest,'label_edges_in_message_passing':False,'llm':'disabled; deterministic agents','unsupported_models':['Node2Vec','GraphSAGE','ComplEx'],'explanation':'Actual graph paths and bounded single-edge occlusion on the trained model; no SHAP, Integrated Gradients or GNNExplainer.'}

@app.get('/api/model/metrics')
@app.get('/api/models/metrics')
def metrics():
    if not app.state.model.report:raise HTTPException(404,'No measured evaluation yet')
    return app.state.model.report

async def train_job(id,request):
    async with app.state.model_lock:
        app.state.store.update(id,status='running')
        try:
            report=await asyncio.to_thread(app.state.model.train,request.epochs,request.seed)
            app.state.store.update(id,status='complete',result=report)
        except Exception as e:app.state.store.update(id,status='failed',error=str(e))

@app.post('/api/model/train',status_code=202)
@app.post('/api/models/train',status_code=202)
def train(request:TrainRequest,background:BackgroundTasks):
    id=str(uuid4());app.state.store.create_job(id,'training',request.model_dump())
    background.add_task(train_job,id,request)
    return {'job_id':id,'status':'queued'}

@app.post('/api/sources/{source}/search')
async def retrieve(source:str,request:RetrievalRequest):
    if source not in app.state.clients:raise HTTPException(404,'Unknown source')
    try:return await app.state.clients[source].search(request.query,request.page)
    except ValueError as e:raise HTTPException(422,str(e))
    except httpx.HTTPError:raise HTTPException(502,'Source unavailable; no substitute evidence generated')

@app.get('/api/sources')
def sources():return {'available':list(CLIENTS),'restricted_not_implemented':['DrugBank','DisGeNET','OMIM','KEGG'],'warning':'Retrieved records require relevance and licensing review before graph ingestion.'}

async def ingest_job(id,request):
    from .ingestion import BiomedicalIngestor
    app.state.store.update(id,status='running')
    try:
        async with app.state.ingest_lock:
            manifest=await BiomedicalIngestor(ROOT/'data/real').acquire(request.disease_ids,request.target_limit,request.drugs_per_disease)
        app.state.store.update(id,status='complete',result=manifest)
    except (httpx.HTTPError,ValueError,KeyError,TypeError,OSError):
        logger.exception('Ingestion job failed: %s',id)
        app.state.store.update(id,status='failed',error='Source retrieval or normalization failed. See server logs; active graph unchanged.')

@app.post('/api/data/ingest',status_code=202)
def ingest(request:IngestRequest,background:BackgroundTasks):
    id=str(uuid4());app.state.store.create_job(id,'ingestion',request.model_dump())
    background.add_task(ingest_job,id,request)
    return {'job_id':id,'status':'queued'}

@app.post('/api/graph/build')
async def build(request:BuildRequest):
    from .schemas import Dataset
    import hashlib,json
    directory=ROOT/'data/real'/request.snapshot_id
    if not (directory/'dataset.json').exists():raise HTTPException(404,'Unknown ingested snapshot')
    async with app.state.model_lock:
        try:
            raw=(directory/'raw.json').read_text(encoding='utf-8')
            if hashlib.sha256(json.dumps(json.loads(raw),sort_keys=True).encode()).hexdigest()!=request.snapshot_id:
                raise ValueError('Raw snapshot hash mismatch')
            from .ingestion import BiomedicalIngestor
            from .connectors import SourceEnvelope
            envelopes=[SourceEnvelope.model_validate(item) for item in json.loads(raw)]
            # Rebuild from raw records instead of trusting an edited normalized file.
            dataset,_=BiomedicalIngestor.normalize(envelopes,set())
            kg=KnowledgeGraph(dataset)
            model=ModelService(kg,Path(os.getenv('MODEL_DIRECTORY',ROOT/'models/checkpoints')))
            normalized=directory/'dataset.tmp'
            normalized.write_text(dataset.model_dump_json(indent=2),encoding='utf-8')
            normalized.replace(directory/'dataset.json')
            if app.state.neo4j_store:await asyncio.to_thread(app.state.neo4j_store.sync,kg)
            await asyncio.to_thread(app.state.store.seed,kg)
        except (ValueError,KeyError,OSError):raise HTTPException(422,'Snapshot validation failed')
        # Restarts select the same snapshot unless DATASET_PATH explicitly overrides it.
        pointer=ROOT/'runtime/active-dataset.tmp'
        pointer.write_text(json.dumps({'snapshot_id':request.snapshot_id}),encoding='utf-8')
        pointer.replace(ROOT/'runtime/active-dataset.json')
        app.state.kg=kg;app.state.model=model
        app.state.orchestrator=Orchestrator(kg,model,app.state.store)
        return {'graph':kg.statistics(),'trained_checkpoint':model.model is not None}

@app.post('/api/models/evaluate')
async def evaluate():
    from .evaluation import evaluate_checkpoint
    async with app.state.model_lock:
        if app.state.model.model is None:raise HTTPException(409,'Train a matching checkpoint first')
        return await asyncio.to_thread(evaluate_checkpoint,app.state.model)

if (ROOT/'frontend/dist').exists():
    app.mount('/',StaticFiles(directory=ROOT/'frontend/dist',html=True),name='dashboard')
