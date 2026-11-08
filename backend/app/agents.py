"""Nine deterministic agents consume computed graph/model results.

No LLM narrative is allowed to introduce biomedical evidence.
"""
import asyncio
import time
from typing import TypedDict
import networkx as nx
from .schemas import PredictRequest

class AgentState(TypedDict):
    disease_id: str
    candidates: list[dict]
    disease: dict
    quality: dict

class Orchestrator:
    names=['Disease analysis','Drug knowledge','Knowledge graph analysis','Graph machine learning','Literature evidence','Safety and pharmacology','Candidate ranking','Explainability','Validation and quality control']

    def __init__(self,kg,model,store):
        self.kg=kg;self.model=model;self.store=store
        from .evidence import EvidenceService
        self.evidence=EvidenceService()

    async def run(self,job_id,request: PredictRequest):
        state: AgentState={'disease_id':request.disease_id,'candidates':[],'disease':{},'quality':{}}
        self.store.update(job_id,status='running')
        try:
            for index,name in enumerate(self.names):
                start=time.perf_counter()
                summary=await asyncio.wait_for(asyncio.to_thread(self.step,index,state,request),timeout=120)
                self.store.log(job_id,name,time.perf_counter()-start,summary)
            self.store.update(job_id,status='complete',result={'disease':state['disease'],'candidates':state['candidates'][:request.limit],'quality':state['quality'],'weights':request.weights,'graph':self.kg.statistics(),'label':'Computational prioritization hypotheses; experimental and clinical validation required.'})
        except Exception as exc:
            self.store.update(job_id,status='failed',error=str(exc))
            self.store.log(job_id,self.names[index],time.perf_counter()-start,{'error':str(exc)},'failed')

    def step(self,index,state,request):
        kg=self.kg;disease=state['disease_id'];candidates=state['candidates']
        if index==0:
            entity=kg.resolve(disease,'Disease');state['disease_id']=entity.id
            state['disease']=entity.model_dump()
            subnet=kg.subgraph(entity.id)
            state['disease']['associated_entities']=subnet['nodes']
            return {'disease_id':entity.id,'associated_entities':len(subnet['nodes'])}
        disease=state['disease_id']
        if index==1:
            known={u for u,v,d in kg.graph.edges(data=True) if v==disease and d['relation'] in {'TREATS','INVESTIGATED_IN'}}
            state['candidates']=[{'drug_id':e.id,'drug_name':e.name,'synthetic':e.synthetic,'targets':[v for _,v,d in kg.graph.out_edges(e.id,data=True) if d['relation'] in ['TARGETS','INHIBITS','ACTIVATES']]} for e in kg.entities.values() if e.kind=='Drug' and e.id not in known]
            return {'candidates':len(state['candidates']),'excluded_known_indications':len(known)}
        if index==2:
            g=kg.analysis_graph();pr=nx.pagerank(g);centrality=nx.degree_centrality(g);between=nx.betweenness_centrality(g)
            communities=list(nx.community.greedy_modularity_communities(g))
            membership={node:i for i,community in enumerate(communities) for node in community}
            personalized=nx.pagerank(g,personalization={node:float(node==disease) for node in g})
            for c in candidates:
                c['graph_paths']=kg.paths(c['drug_id'],disease)
                c['centrality_features']={'degree':centrality[c['drug_id']],'pagerank':pr[c['drug_id']],'betweenness':between[c['drug_id']],'disease_personalized_pagerank':personalized[c['drug_id']],'community':membership[c['drug_id']]}
                c['common_neighbors']=sorted(set(g[c['drug_id']])&set(g[disease]))
                c['network_score']=max([1/(len(p['nodes'])-1) for p in c['graph_paths']],default=0)
            return {'paths':sum(len(c['graph_paths']) for c in candidates),'indication_edges_excluded':True}
        if index==3:
            for c in candidates:
                c['prediction_score']=self.model.score(c['drug_id'],disease)
                c['model_name']='R-GCN + DistMult';c['model_version']='1'
            return {'checkpoint_graph_sha256':kg.digest,'scored':len(candidates)}
        if index==4:
            # Fixture identifiers must never be submitted to biomedical searches.
            real=sorted([c for c in candidates if not c['synthetic']],key=lambda c:-c['prediction_score'])[:3]
            retrieved=asyncio.run(self.evidence.retrieve_candidates(real,state['disease']['name'],'literature')) if real else {}
            for c in candidates:
                found=retrieved.get(c['drug_id'],{'status':'not_retrieved','publications':[]})
                c['publications']=found['publications']
                c['literature_status']=found['status']
            return {'publications':sum(len(c['publications']) for c in candidates),'retrieval_limit':3,'reason':'Synthetic entities are not queried. Real search hits require relevance/polarity review and contribute zero literature support.'}
        if index==5:
            real=sorted([c for c in candidates if not c['synthetic']],key=lambda c:-c['prediction_score'])[:3]
            retrieved=asyncio.run(self.evidence.retrieve_candidates(real,state['disease']['name'],'safety')) if real else {}
            for c in candidates:
                c['safety']=retrieved.get(c['drug_id'],{'status':'not_retrieved','evidence':[],'data_gaps':['No validated safety, contraindication, interaction or PK/PD dataset loaded.'],'warnings':['Computational score cannot establish clinical safety.']})
            return {'safety_evidence':sum(len(c['safety']['evidence']) for c in candidates),'data_gap':True,'retrieval_limit':3}
        if index==6:
            for c in candidates:
                provenances=[e['provenance'] for p in c['graph_paths'] for e in p['edges']]
                completeness=float(bool(provenances) and all(p.get('source') and p.get('record_id') and p.get('reference') for p in provenances))
                c['components']={'model':c['prediction_score'],'network':c['network_score'],'literature':0.0,'pharmacology':0.0,'completeness':completeness}
                c['score']=sum(request.weights[k]*v for k,v in c['components'].items())
            candidates.sort(key=lambda c:(-c['score'],c['drug_id']))
            for rank,c in enumerate(candidates,1):c['rank']=rank
            return {'ranked':len(candidates),'missing_evidence_components': ['literature','pharmacology']}
        if index==7:
            for c in candidates:
                ids={n for p in c['graph_paths'] for n in p['nodes']}
                c['explanation']={'text':f"Ranked using trained graph model output and {len(c['graph_paths'])} retrieved connectivity paths. These paths do not establish a therapeutic mechanism.",'important_genes':[i for i in ids if kg.entities[i].kind=='Gene'],'important_proteins':[i for i in ids if kg.entities[i].kind=='Protein'],'pathways':[i for i in ids if kg.entities[i].kind=='Pathway'],'limitations':['No clinical efficacy inference.','Graph connectivity is not causal evidence.','Missing literature and pharmacology support score zero.','No GNN attribution computed; paths are post-hoc graph explanations.']}
                c['explanation']['model_sensitivity']=self.model.explain_edges(c['drug_id'],disease,c['graph_paths'])
                c['explanation']['limitations'][-1]='Single-edge occlusion measures model sensitivity on a bounded path subgraph; it is not biological causation.'
            return {'explained':len(candidates),'methods':['retrieved paths','transparent ranking components','trained-model single-edge occlusion']}
        for c in candidates:
            if not 0<=c['score']<=1:raise ValueError('Invalid prioritization score')
            for path in c['graph_paths']:
                for e in path['edges']:
                    if not e['provenance']['reference']:raise ValueError('Untraceable evidence')
                    if e['provenance']['synthetic']!=c['synthetic']:raise ValueError('Mixed synthetic/real evidence requires curated validation')
        state['quality']={'passed':True,'evidence_sufficient_for_efficacy':False,'missing_safety':any(not c['safety']['evidence'] for c in candidates),'publication_claims':0,'scope':'Identifier, score and path provenance checks; not scientific validation.'}
        return state['quality']
