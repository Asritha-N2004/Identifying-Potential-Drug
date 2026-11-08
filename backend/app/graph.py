"""Provenance-preserving graph queries and strict identifier resolution."""
import hashlib
import json
from pathlib import Path
import networkx as nx
from .schemas import Dataset

class KnowledgeGraph:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        self.entities = {e.id:e for e in dataset.entities}
        self.graph = nx.MultiDiGraph(version=dataset.version)
        for e in dataset.entities:
            self.graph.add_node(e.id, **e.model_dump(exclude={'id'}))
        seen = set()
        for e in dataset.relationships:
            key = (e.source,e.target,e.relation,e.provenance.source,e.provenance.record_id)
            if key not in seen:
                self.graph.add_edge(e.source,e.target, **e.model_dump(exclude={'source','target'},mode='json'))
                seen.add(key)
        raw = json.dumps(dataset.model_dump(mode='json'),sort_keys=True).encode()
        self.digest = hashlib.sha256(raw).hexdigest()

    @classmethod
    def load(cls, path: Path):
        return cls(Dataset.model_validate_json(path.read_text(encoding='utf-8')))

    def resolve(self, text: str, kind: str):
        exact = [e for e in self.entities.values() if e.kind==kind and (e.id==text or text.casefold() in [s.casefold() for s in [e.name,*e.synonyms]])]
        if len(exact)!=1:
            raise ValueError('Entity not found or ambiguous; use a canonical identifier')
        return exact[0]

    def analysis_graph(self):
        """Exclude indication labels from inference graph and path explanations."""
        g = nx.Graph()
        g.add_nodes_from(self.graph.nodes)
        for u,v,d in self.graph.edges(data=True):
            if d['relation'] not in {'TREATS','INVESTIGATED_IN'}:
                g.add_edge(u,v)
        return g

    def paths(self, source: str, target: str, limit=5):
        from itertools import islice
        g = self.analysis_graph()
        if source not in g or target not in g:
            return []
        try:
            paths = islice(nx.shortest_simple_paths(g,source,target),limit)
            results = []
            for path in paths:
                if len(path)>6:
                    break
                edges=[]
                for a,b in zip(path,path[1:]):
                    records = [(a,b,d,True) for d in self.graph.get_edge_data(a,b,default={}).values() if d['relation'] not in {'TREATS','INVESTIGATED_IN'}]
                    records += [(b,a,d,False) for d in self.graph.get_edge_data(b,a,default={}).values() if d['relation'] not in {'TREATS','INVESTIGATED_IN'}]
                    u,v,d,forward=records[0]
                    edges.append({'source':u,'target':v,'traversed_forward':forward,**d})
                results.append({'nodes':path,'edges':edges,'interpretation':'Connectivity only; direction and causal effect require review.'})
            return results
        except nx.NetworkXNoPath:
            return []

    def subgraph(self, entity_id: str):
        g = self.analysis_graph()
        ids={entity_id,*g.neighbors(entity_id)}
        return {'nodes':[self.entities[i].model_dump() for i in sorted(ids)],'edges':[{'source':u,'target':v,**d} for u,v,d in self.graph.edges(data=True) if u in ids and v in ids]}

    def statistics(self):
        from collections import Counter
        g=self.analysis_graph()
        edges=list(self.graph.edges(data=True))
        return {'nodes':len(self.entities),'edges':len(edges),'version':self.dataset.version,'sha256':self.digest,'synthetic':all(e.synthetic for e in self.entities.values()),
                'entity_distribution':dict(Counter(e.kind for e in self.entities.values())),
                'relationship_distribution':dict(Counter(d['relation'] for _,_,d in edges)),
                'degree_distribution':dict(Counter(dict(g.degree()).values())),
                'connected_components':nx.number_connected_components(g),'isolated_nodes':list(nx.isolates(g)),
                'provenance_coverage':sum(bool(d.get('provenance',{}).get('source')) for _,_,d in edges)/max(1,len(edges)),
                'topology_scope':'Undirected projection excluding TREATS and INVESTIGATED_IN clinical labels'}
