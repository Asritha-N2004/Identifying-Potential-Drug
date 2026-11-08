"""Reproducible relation-aware GNN training with label-free message passing."""
import json
import os
from pathlib import Path
import numpy as np
import torch
from torch import nn
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, precision_recall_curve
from sklearn.model_selection import train_test_split
import networkx as nx

class RGCN(nn.Module):
    """Two relation-specific message-passing layers and DistMult decoder.

    Includes explicit inverse relation types for non-indication edges only.
    All approved/investigational clinical labels are excluded in every split.
    """
    def __init__(self, nodes: int, relations: int, dim=24):
        super().__init__()
        self.embedding=nn.Embedding(nodes,dim)
        self.layers=nn.ParameterList([nn.Parameter(torch.randn(relations,dim,dim)*.08) for _ in range(2)])
        self.self_layers=nn.ModuleList([nn.Linear(dim,dim) for _ in range(2)])
        self.decoder=nn.Parameter(torch.ones(dim))

    def encode(self, edge_index, edge_type):
        h=self.embedding.weight
        src,dst=edge_index
        for weights,own in zip(self.layers,self.self_layers):
            aggregate=torch.zeros_like(h)
            for r in range(weights.shape[0]):
                mask=edge_type==r
                messages=h[src[mask]] @ weights[r]
                normalized=torch.bincount(dst[mask],minlength=len(h)).clamp(min=1).float().unsqueeze(1)
                result=torch.zeros_like(h)
                result.index_add_(0,dst[mask],messages)
                aggregate=aggregate+result/normalized
            h=torch.relu(own(h)+aggregate)
        return h

    def forward(self, edge_index, edge_type, pairs):
        h=self.encode(edge_index,edge_type)
        return (h[pairs[:,0]]*self.decoder*h[pairs[:,1]]).sum(-1)

class ModelService:
    def __init__(self,kg, directory: Path):
        # Small CPU graphs otherwise oversubscribe scatter/gather worker threads.
        torch.set_num_threads(max(1,min(32,int(os.getenv('ML_NUM_THREADS','1')))))
        self.kg=kg
        self.directory=directory
        # Unreviewed publication metadata is context, not a predictive entity.
        # Excluding it also prevents unrelated metadata nodes from changing seeded initialization.
        self.ids=sorted(e.id for e in kg.entities.values() if e.kind!='Publication')
        self.index={x:i for i,x in enumerate(self.ids)}
        triples=[(u,v,d['relation']) for u,v,d in kg.graph.edges(data=True) if d['relation'] not in {'TREATS','INVESTIGATED_IN'} and u in self.index and v in self.index]
        relations=sorted({r for _,_,r in triples})
        self.relations=relations
        if not relations:
            raise ValueError('At least one non-indication relationship is required for graph learning')
        edges=[]; types=[]
        for u,v,r in triples:
            edges.extend([(self.index[u],self.index[v]),(self.index[v],self.index[u])])
            types.extend([relations.index(r),relations.index(r)+len(relations)])
        self.edge_index=torch.tensor(edges,dtype=torch.long).T.contiguous()
        self.edge_type=torch.tensor(types,dtype=torch.long)
        self.model=None
        self.report=None
        checkpoint=directory/'rgcn.pt'
        if checkpoint.exists():
            saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
            if saved['graph_sha256']==kg.digest and saved['ids']==self.ids:
                self.model=RGCN(len(self.ids),len(relations)*2)
                self.model.load_state_dict(saved['state_dict'])
                self.model.eval()
                self.report=json.loads((directory/'evaluation.json').read_text())

    def features(self,pairs):
        g=self.kg.analysis_graph()
        result=[]
        personalized={b:nx.pagerank(g,personalization={n:float(n==b) for n in g}) for b in {b for _,b in pairs}}
        for a,b in pairs:
            na=set(g[a]);nb=set(g[b]);common=na&nb
            try: distance=nx.shortest_path_length(g,a,b)
            except nx.NetworkXNoPath: distance=100
            result.append([len(common),len(common)/max(1,len(na|nb)),sum(1/np.log(max(2,g.degree(c))) for c in common),1/(1+distance),g.degree(a),g.degree(b),sum(1/g.degree(c) for c in common),personalized[b][a]])
        return np.array(result,dtype=float)

    def train(self,epochs=60,seed=42):
        torch.set_num_threads(1)
        torch.manual_seed(seed)
        rng=np.random.default_rng(seed)
        drugs=[e.id for e in self.kg.entities.values() if e.kind=='Drug']
        diseases=[e.id for e in self.kg.entities.values() if e.kind=='Disease']
        positives=sorted({(u,v) for u,v,d in self.kg.graph.edges(data=True) if d['relation']=='TREATS'})
        if len(positives)<12:
            raise ValueError('At least 12 distinct positive pairs required')
        clinical={(u,v) for u,v,d in self.kg.graph.edges(data=True) if d['relation'] in {'TREATS','INVESTIGATED_IN'}}
        unknown=[(a,b) for a in drugs for b in diseases if (a,b) not in clinical]
        if len(unknown)<len(positives):
            raise ValueError('Insufficient disjoint unlabeled controls')
        controls=[unknown[i] for i in rng.choice(len(unknown),len(positives),replace=False)]
        pairs=positives+controls
        y=np.array([1]*len(positives)+[0]*len(controls))
        indices=np.arange(len(pairs))
        train,temp=train_test_split(indices,test_size=.4,stratify=y,random_state=seed)
        val,test=train_test_split(temp,test_size=.5,stratify=y[temp],random_state=seed)
        x=torch.tensor([[self.index[a],self.index[b]] for a,b in pairs])
        labels=torch.tensor(y,dtype=torch.float32)
        model=RGCN(len(self.ids),len(self.relations)*2)
        optimizer=torch.optim.Adam(model.parameters(),lr=.01,weight_decay=1e-4)
        history=[];best=float('inf');best_state=None;stale=0
        for epoch in range(epochs):
            model.train();optimizer.zero_grad()
            logits=model(self.edge_index,self.edge_type,x)
            loss=nn.functional.binary_cross_entropy_with_logits(logits[train],labels[train])
            loss.backward();optimizer.step()
            model.eval()
            with torch.no_grad():
                validation=nn.functional.binary_cross_entropy_with_logits(model(self.edge_index,self.edge_type,x[val]),labels[val]).item()
            history.append({'epoch':epoch+1,'train_loss':loss.item(),'validation_loss':validation})
            if validation < best-1e-5:
                best=validation;best_state={k:v.detach().clone() for k,v in model.state_dict().items()};stale=0
            else: stale+=1
            if stale>=12: break
        model.load_state_dict(best_state);model.eval()
        self.model=model
        features=self.features(pairs)
        predictions={}
        with torch.no_grad():
            predictions['R-GCN']=torch.sigmoid(model(self.edge_index,self.edge_type,x[test])).numpy()
        for name,baseline in [('Logistic regression',LogisticRegression(random_state=seed,max_iter=500)),('Random forest',RandomForestClassifier(n_estimators=80,max_depth=4,random_state=seed))]:
            baseline.fit(features[train],y[train]);predictions[name]=baseline.predict_proba(features[test])[:,1]
        for name,column in [('Common neighbors',0),('Jaccard',1),('Adamic-Adar',2),('Resource allocation',6),('Personalized PageRank',7)]:
            predictions[name]=features[test,column]
        for name,columns in [('Logistic regression: topology only',[0,1,2,3,6,7]),('Logistic regression: degree only',[4,5])]:
            baseline=LogisticRegression(random_state=seed,max_iter=500)
            baseline.fit(features[train][:,columns],y[train])
            predictions[name]=baseline.predict_proba(features[test][:,columns])[:,1]
        metrics={}
        for name,scores in predictions.items():
            order=np.argsort(-scores,kind='stable');relevant=y[test][order];k=min(10,len(order))
            ranks=np.flatnonzero(relevant)+1
            fpr,tpr,_=roc_curve(y[test],scores)
            precision,recall,_=precision_recall_curve(y[test],scores)
            metrics[name]={'roc_auc':float(roc_auc_score(y[test],scores)),'average_precision':float(average_precision_score(y[test],scores)),'precision_at_10':float(relevant[:k].mean()),'recall_at_10':float(relevant[:k].sum()/max(1,relevant.sum())),'hit_at_10':bool(relevant[:k].any()),'reciprocal_rank':float(1/ranks[0]) if len(ranks) else 0,'roc':{'x':fpr.tolist(),'y':tpr.tolist()},'pr':{'x':recall.tolist(),'y':precision.tolist()}}
        self.report={'dataset_version':self.kg.dataset.version,'graph_sha256':self.kg.digest,'synthetic':all(e.synthetic for e in self.kg.entities.values()),'seed':seed,'model':'R-GCN + DistMult','version':'1','epochs_requested':epochs,'history':history,'split':{'train':len(train),'validation':len(val),'test':len(test)},'metrics':metrics,'limitations':['Sampled unlabeled controls are not confirmed negatives.','Random pair split only; no temporal or cold-start validation.','Pooled ranking metrics apply to the sampled test set, not disease-specific retrieval.','Synthetic fixture results do not estimate biomedical performance.','No calibrated clinical probabilities or confidence intervals.'],'split_pairs':{name:[{'drug':pairs[i][0],'disease':pairs[i][1],'label':int(y[i])} for i in idx] for name,idx in [('train',train),('validation',val),('test',test)]}}
        if not self.report['synthetic']:
            self.report['limitations']=[s for s in self.report['limitations'] if 'Synthetic fixture' not in s]
            self.report['limitations'].extend(['Bounded disease/drug selection creates ascertainment bias.',
                'Genetic datatype scores exclude known-drug support, but aggregate-ranked target selection can retain selection bias.',
                'All approved and investigational clinical edges are excluded from graph features; clinical pairs are excluded from unlabeled controls.'])
        self.directory.mkdir(parents=True,exist_ok=True)
        torch.save({'state_dict':model.state_dict(),'graph_sha256':self.kg.digest,'ids':self.ids},self.directory/'rgcn.pt')
        (self.directory/'evaluation.json').write_text(json.dumps(self.report,indent=2))
        return self.report

    def score(self,drug,disease):
        if self.model is None:
            raise ValueError('No matching trained checkpoint; train the model first')
        with torch.no_grad():
            pair=torch.tensor([[self.index[drug],self.index[disease]]])
            return torch.sigmoid(self.model(self.edge_index,self.edge_type,pair)).item()

    def explain_edges(self,drug,disease,paths,limit=12):
        """Exact single-edge occlusion sensitivity on the trained model.

        Remove both forward and inverse message-passing instances of an edge.
        This explains computational sensitivity, never a biological causal effect.
        """
        if self.model is None:raise ValueError('A trained model is required')
        base=self.score(drug,disease)
        unique={}
        for path in paths:
            for edge in path['edges']:
                key=(edge['source'],edge['target'],edge['relation'])
                unique[key]=edge
        results=[]
        pair=torch.tensor([[self.index[drug],self.index[disease]]])
        with torch.no_grad():
            for (u,v,relation),edge in list(unique.items())[:limit]:
                r=self.relations.index(relation);src,dst=self.edge_index
                forward=(src==self.index[u])&(dst==self.index[v])&(self.edge_type==r)
                inverse=(src==self.index[v])&(dst==self.index[u])&(self.edge_type==r+len(self.relations))
                keep=~(forward|inverse)
                occluded=torch.sigmoid(self.model(self.edge_index[:,keep],self.edge_type[keep],pair)).item()
                results.append({'source':u,'target':v,'relation':relation,'original_score':base,'occluded_score':occluded,'score_difference':base-occluded,'provenance':edge['provenance']})
        results.sort(key=lambda x:-abs(x['score_difference']))
        return {'method':'single_edge_occlusion','edges':results,'evaluated_edges':len(results),'edge_limit':limit,'scope':'Only edges from retrieved paths, not an exhaustive graph explanation. Scores are recomputed without retraining. No biological causal interpretation.'}
