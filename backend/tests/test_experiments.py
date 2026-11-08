"""Regression checks for measured baselines and ranking diagnostics."""
from pathlib import Path
import numpy as np
import networkx as nx
import pytest
from backend.app.graph import KnowledgeGraph
from backend.app.ml import ModelService
from backend.app.schemas import Entity
from scripts.run_experiments import sensitivity

ROOT = Path(__file__).resolve().parents[2]


def test_structural_features_exclude_labels(tmp_path):
    kg = KnowledgeGraph.load(ROOT/'data/sample/synthetic.json')
    model = ModelService(kg, tmp_path)
    pair = ('SYNTHETIC:Drug:0', 'SYNTHETIC:Disease:0')
    g = kg.analysis_graph()
    features = model.features([pair])[0]
    assert features[6] == pytest.approx(next(nx.resource_allocation_index(g, [pair]))[2])
    assert features[7] == pytest.approx(nx.pagerank(g, personalization={n:float(n == pair[1]) for n in g})[pair[0]])
    assert np.isfinite(features).all()
    stats = kg.statistics()
    assert sum(stats['entity_distribution'].values()) == stats['nodes']
    assert sum(stats['relationship_distribution'].values()) == stats['edges']
    assert stats['provenance_coverage'] == 1


def test_sensitivity_recomputes_rank_without_mutation():
    weights = {'model': .5, 'network': .5}
    candidates = [{'drug_id':'a', 'components':{'model':1, 'network':0}},
                  {'drug_id':'b', 'components':{'model':0, 'network':1}}]
    report = sensitivity(candidates, weights)
    assert len(report) == 4
    assert any(row['max_rank_shift'] == 1 for row in report)
    assert all(sum(row['weights'].values()) == pytest.approx(1) for row in report)
    assert weights == {'model':.5, 'network':.5}


def test_context_publications_do_not_change_predictive_graph(tmp_path):
    import torch
    kg=KnowledgeGraph.load(ROOT/'data/sample/synthetic.json')
    data=kg.dataset.model_copy(deep=True)
    data.entities.append(Entity(id='SYNTHETIC:Publication:mock',name='Mock context only',kind='Publication',synthetic=True))
    original=ModelService(kg,tmp_path/'original')
    augmented=ModelService(KnowledgeGraph(data),tmp_path/'augmented')
    assert original.ids==augmented.ids
    assert torch.equal(original.edge_index,augmented.edge_index)
    assert torch.equal(original.edge_type,augmented.edge_type)
