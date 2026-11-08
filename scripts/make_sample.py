"""Generate a deterministic, wholly fictional graph, never biomedical evidence."""
import json
from pathlib import Path

def build():
    entities=[]
    edges=[]
    for kind,count in [('Drug',24),('Disease',8),('Gene',16),('Protein',16),('Pathway',4),('BiologicalProcess',4)]:
        for i in range(count):
            entities.append({'id':f'SYNTHETIC:{kind}:{i}','name':f'Synthetic {kind} {i+1:02d}','kind':kind,'synthetic':True,'synonyms':[],'attributes':{}})
    def edge(a,b,relation):
        n=len(edges)
        edges.append({'source':a,'target':b,'relation':relation,'description':f'SYNTHETIC fixture relationship {n}; no biological claim','provenance':{'source':'SYNTHETIC','record_id':f'fixture-{n}','reference':f'fixture://v1/{n}','retrieved_at':'2026-01-01T00:00:00Z','evidence_type':'synthetic','license':'CC0-1.0','synthetic':True}})
    for i in range(16):
        edge(f'SYNTHETIC:Protein:{i}',f'SYNTHETIC:Gene:{i}','ENCODED_BY')
        edge(f'SYNTHETIC:Protein:{i}',f'SYNTHETIC:Pathway:{i%4}','PARTICIPATES_IN')
        edge(f'SYNTHETIC:Gene:{i}',f'SYNTHETIC:Disease:{i%8}','ASSOCIATED_WITH')
    for i in range(8):
        edge(f'SYNTHETIC:Disease:{i}',f'SYNTHETIC:Pathway:{i%4}','ASSOCIATED_WITH')
        edge(f'SYNTHETIC:Pathway:{i%4}',f'SYNTHETIC:BiologicalProcess:{i%4}','PARTICIPATES_IN')
    for i in range(24):
        edge(f'SYNTHETIC:Drug:{i}',f'SYNTHETIC:Protein:{i%16}','TARGETS')
        edge(f'SYNTHETIC:Drug:{i}',f'SYNTHETIC:Disease:{i%8}','TREATS')
        edge(f'SYNTHETIC:Drug:{i}',f'SYNTHETIC:Disease:{(i+4)%8}','TREATS')
    # Connect fictional modules so unknown pairs can have inspectable paths.
    for i in range(16):
        edge(f'SYNTHETIC:Protein:{i}',f'SYNTHETIC:Protein:{(i+1)%16}','INTERACTS_WITH')
        edges[-1]['directed']=False
    return {'version':'synthetic-v2','entities':entities,'relationships':edges}

if __name__=='__main__':
    path=Path(__file__).resolve().parents[1]/'data/sample/synthetic.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(build(),indent=2),encoding='utf-8')
    print(path)
