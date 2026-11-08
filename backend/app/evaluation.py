"""Reevaluate the trained model on its original held-out pairs, without training."""
import numpy as np
import torch
from sklearn.metrics import roc_auc_score, average_precision_score


def evaluate_checkpoint(service):
    if service.model is None or not service.report:
        raise ValueError('No matching checkpoint available')
    report=service.report
    if report['graph_sha256'] != service.kg.digest:
        raise ValueError('Checkpoint graph mismatch')
    splits=report['split_pairs']
    sets=[{(p['drug'],p['disease']) for p in splits[name]} for name in ['train','validation','test']]
    if any(sets[i]&sets[j] for i in range(3) for j in range(i)):
        raise ValueError('Evaluation split overlap')
    rows=splits['test']
    pairs=torch.tensor([[service.index[p['drug']],service.index[p['disease']]] for p in rows])
    labels=np.array([p['label'] for p in rows])
    service.model.eval()
    with torch.no_grad():
        scores=torch.sigmoid(service.model(service.edge_index,service.edge_type,pairs)).numpy()
    relevant=labels[np.argsort(-scores,kind='stable')]; k=min(10,len(relevant)); ranks=np.flatnonzero(relevant)+1
    metrics={'roc_auc':float(roc_auc_score(labels,scores)),'average_precision':float(average_precision_score(labels,scores)),
             'precision_at_10':float(relevant[:k].mean()),'recall_at_10':float(relevant[:k].sum()/max(1,relevant.sum())),
             'hit_at_10':bool(relevant[:k].any()),'reciprocal_rank':float(1/ranks[0]) if len(ranks) else 0}
    per_disease={}
    for disease in sorted({row['disease'] for row in rows}):
        mask=np.array([row['disease']==disease for row in rows])
        truth=labels[mask]; predicted=scores[mask]
        per_disease[disease]={'test_pairs':int(mask.sum()),'positives':int(truth.sum()),
            'roc_auc':float(roc_auc_score(truth,predicted)) if len(set(truth))==2 else None,
            'average_precision':float(average_precision_score(truth,predicted)) if truth.sum() else None}
    return {'graph_sha256':service.kg.digest,'model':'R-GCN + DistMult','synthetic':report['synthetic'],
            'split':report['split'],'metrics':{'R-GCN':metrics},'per_disease':per_disease,'test_pairs':rows,'scores':scores.tolist(),
            'protocol':'Recomputed original held-out test predictions; no training or split selection.',
            'limitations':report['limitations']+['Repeat evaluation is not an independent replication.']}
