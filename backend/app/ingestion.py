"""Bounded Open Targets ETL; source records are associations, not efficacy claims."""
import hashlib
import json
from pathlib import Path
from .connectors import OpenTargets, EuropePMC
from .schemas import Dataset, Entity, Relationship, Provenance

ENDPOINT = 'https://api.platform.opentargets.org/api/v4/graphql'
CASE_IDS = ['MONDO_0008383', 'MONDO_0005083', 'MONDO_0005265']
TARGET_FIELDS = 'id approvedSymbol pathways{pathwayId pathway} proteinIds{id source}'
DISEASE_QUERY = '''query Case($id:String!,$n:Int!){disease(efoId:$id){id name
 associatedTargets(enableIndirect:false,page:{index:0,size:$n}){count rows{score datatypeScores{id score} datasourceScores{id score} target{''' + TARGET_FIELDS + '''}}}
 drugAndClinicalCandidates{count rows{id maxClinicalStage drug{id name}}}}}'''
DRUG_QUERY = '''query Drug($id:String!){drug(chemblId:$id){id name maximumClinicalStage
 mechanismsOfAction{rows{actionType mechanismOfAction targets{''' + TARGET_FIELDS + '''}}}}}'''


class BiomedicalIngestor:
    def __init__(self, directory: Path, client=None, literature=None):
        self.directory = directory
        self.client = client or OpenTargets()
        self.literature = literature or EuropePMC()

    async def graphql(self, query, variables):
        envelope = await self.client.request(ENDPOINT, body={'query':query, 'variables':variables})
        if not isinstance(envelope.payload, dict) or not envelope.payload.get('data'):
            raise ValueError('Open Targets response contains no data')
        return envelope

    async def acquire(self, disease_ids, targets=100, drugs_per_disease=20):
        """Write an immutable content-addressed snapshot, leaving active graph untouched."""
        envelopes = []; cases = []; drug_ids = set()
        for disease_id in disease_ids:
            env = await self.graphql(DISEASE_QUERY, {'id':disease_id, 'n':targets})
            disease = env.payload['data'].get('disease')
            if not disease: raise ValueError(f'Unknown disease identifier: {disease_id}')
            envelopes.append(env); cases.append(disease)
            rows = disease['drugAndClinicalCandidates']['rows']
            approved = sorted({r['drug']['id'] for r in rows if r.get('drug') and r['maxClinicalStage'].upper() in {'APPROVED','APPROVAL'}})
            drug_ids.update(approved[:drugs_per_disease])
        for drug_id in sorted(drug_ids):
            envelopes.append(await self.graphql(DRUG_QUERY, {'id':drug_id}))
        # Disease-level publications are metadata/context, never inferred support for a drug.
        for disease in cases:
            envelopes.append(await self.literature.search(f'TITLE_ABS:"{disease["name"]}"'))
        dataset, manifest = self.normalize(envelopes, drug_ids)
        raw = [e.model_dump(mode='json',exclude={'cached'}) for e in envelopes]
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        snapshot = self.directory/digest
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot/'raw.json').write_text(json.dumps(raw, indent=2), encoding='utf-8')
        (snapshot/'dataset.json').write_text(dataset.model_dump_json(indent=2), encoding='utf-8')
        manifest.update({'snapshot_id':digest, 'disease_ids':disease_ids, 'target_limit':targets,
                         'drugs_per_disease':drugs_per_disease, 'raw_sha256':digest})
        (snapshot/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest

    @staticmethod
    def normalize(envelopes, selected_drugs):
        entities = {}; edges = []; seen = set(); cases = []
        def node(id, name, kind, **attributes):
            if id not in entities:
                entities[id] = Entity(id=id, name=name, kind=kind, attributes=attributes)
        def edge(a,b,relation,env,record,description,score=None):
            key=(a,b,relation,record)
            if key in seen:return
            seen.add(key)
            edges.append(Relationship(source=a,target=b,relation=relation,description=description,
                provenance=Provenance(source=env.source,record_id=record,reference=env.url,
                  retrieved_at=env.retrieved_at,evidence_type=description,license=env.license,confidence=score)))
        def target(t, env):
            node(t['id'],t['approvedSymbol'],'Gene',external_id=t['id'])
            for protein in t.get('proteinIds', []):
                if protein['source'] != 'uniprot_swissprot': continue
                pid='UniProt:'+protein['id']; node(pid,protein['id'],'Protein',external_id=protein['id'])
                edge(pid,t['id'],'ENCODED_BY',env,pid+':'+t['id'],'Open Targets UniProt cross-reference; not a measured interaction')
            for pathway in t.get('pathways', []):
                pid=pathway['pathwayId']; node(pid,pathway['pathway'],'Pathway',external_id=pid)
                edge(t['id'],pid,'PARTICIPATES_IN',env,t['id']+':'+pid,'Reactome pathway membership via Open Targets')
        for env in envelopes:
            data=env.payload.get('data', {})
            disease=data.get('disease')
            if disease:
                cases.append(disease)
                node(disease['id'],disease['name'],'Disease',external_id=disease['id'])
                for row in disease['associatedTargets']['rows']:
                    # Do not import aggregate associations that can encode drug-indication labels.
                    genetic=next((s['score'] for s in row['datatypeScores'] if s['id']=='genetic_association'),0)
                    if genetic <= 0:continue
                    t=row['target']; target(t,env)
                    edge(t['id'],disease['id'],'ASSOCIATED_WITH',env,t['id']+':'+disease['id'],
                         'Direct genetic-association datatype support only; aggregate/known-drug scores excluded',genetic)
        for env in envelopes:
            drug=env.payload.get('data', {}).get('drug')
            if not drug:continue
            node(drug['id'],drug['name'],'Drug',external_id=drug['id'],maximum_clinical_stage=drug['maximumClinicalStage'])
            for index, mechanism in enumerate((drug.get('mechanismsOfAction') or {}).get('rows', [])):
                for t in mechanism['targets']:
                    target(t,env)
                    edge(drug['id'],t['id'],'TARGETS',env,drug['id']+':'+t['id']+':'+str(index),
                         f"Reported mechanism: {mechanism['mechanismOfAction']}; action={mechanism.get('actionType')}")
        for env in envelopes:
            disease=env.payload.get('data', {}).get('disease')
            if not disease:continue
            for row in disease['drugAndClinicalCandidates']['rows']:
                drug=row.get('drug')
                if not drug or drug['id'] not in entities:continue
                approved=row['maxClinicalStage'].upper() in {'APPROVED','APPROVAL'}
                edge(drug['id'],disease['id'],'TREATS' if approved else 'INVESTIGATED_IN',env,
                     row['id'],f"Source clinical stage: {row['maxClinicalStage']}; not independently verified regulatory labeling")
        # Publication search hits are stored as disconnected context nodes, never efficacy edges.
        for env in envelopes:
            if env.source != 'Europe PMC':continue
            retained=0
            for publication in env.payload.get('resultList', {}).get('result', []):
                if not publication.get('pmid'):continue
                pid='PMID:'+publication['pmid']
                node(pid,publication.get('title') or pid,'Publication',year=publication.get('pubYear'),
                     url='https://pubmed.ncbi.nlm.nih.gov/'+publication['pmid']+'/',
                     retrieval=env.model_dump(mode='json',exclude={'payload','cached'}),evidence_status='Unreviewed disease-context search hit')
                retained+=1
                if retained>=5:break
        dataset=Dataset(version='opentargets-real-v1',entities=list(entities.values()),relationships=edges)
        manifest={'source':'Open Targets + Europe PMC','retrieved_at':[e.retrieved_at for e in envelopes],
                  'cases':[{'id':d['id'],'name':d['name'],'available_targets':d['associatedTargets']['count']} for d in cases],
                  'entities':len(entities),'relationships':len(edges),'selected_drugs':len(selected_drugs),
                  'limitations':['Bounded subset, not a complete catalog.','Clinical stages are source assertions, not jurisdiction-specific approvals.',
                  'Genetic datatype scores exclude known-drug scores but are selected from aggregate-ranked targets; selection bias remains.',
                  'Open Targets aggregates upstream sources; these are not independent replications.','Publication search hits are unreviewed context only.']}
        return dataset,manifest
