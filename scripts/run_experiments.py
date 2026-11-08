"""Three fixture case studies and ranking sensitivity; no clinical assertions."""
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.graph import KnowledgeGraph
from backend.app.ml import ModelService
from backend.app.agents import Orchestrator
from backend.app.schemas import PredictRequest
from backend.app.storage import Store
from backend.app.evaluation import evaluate_checkpoint


def sensitivity(candidates, weights):
    """Perturb each weight +/-20%, normalize, and compare to baseline ranks."""
    def order(w):
        return [c['drug_id'] for c in sorted(candidates, key=lambda c: (-sum(w[k]*c['components'][k] for k in w), c['drug_id']))]
    baseline = order(weights)
    results = []
    for component in weights:
        for factor in (.8, 1.2):
            changed = {k: v*(factor if k == component else 1) for k, v in weights.items()}
            total = sum(changed.values())
            changed = {k: v/total for k, v in changed.items()}
            ranked = order(changed)
            k = min(5, len(ranked))
            results.append({'component': component, 'factor': factor, 'weights': changed,
                            'top_5_overlap': len(set(baseline[:k]) & set(ranked[:k]))/max(1, k),
                            'max_rank_shift': max((abs(i-ranked.index(drug)) for i, drug in enumerate(baseline)), default=0)})
    return results


async def run():
    kg = KnowledgeGraph.load(Path(os.getenv('DATASET_PATH', ROOT/'data/sample/synthetic.json')))
    model = ModelService(kg, Path(os.getenv('MODEL_DIRECTORY', ROOT/'models/checkpoints')))
    if model.model is None:
        raise SystemExit('Train a matching model first.')
    store = Store(); store.seed(kg)
    cases = []
    try:
        for disease in sorted((e for e in kg.entities.values() if e.kind == 'Disease'), key=lambda e:e.id)[:3]:
            print(f'Analyzing {disease.id}: {disease.name}',flush=True)
            request = PredictRequest(disease_id=disease.id, limit=100)
            job = str(uuid4()); store.create_job(job, 'discovery', request.model_dump())
            await Orchestrator(kg, model, store).run(job, request)
            result = store.get(job)
            if result['status'] != 'complete':
                raise RuntimeError(result['error'])
            candidates = result['result']['candidates']
            cases.append({'disease': disease.model_dump(), 'selection_reason': 'First three canonical disease identifiers in the loaded graph; bounded retrospective case studies.',
                          'candidates': candidates, 'weight_sensitivity': sensitivity(candidates, request.weights)})
            print(f'Completed {disease.name}: {len(candidates)} candidates',flush=True)
        report = {'graph': kg.statistics(), 'cases': cases, 'evaluation': model.report,'reevaluation':evaluate_checkpoint(model),
                  'limitations': ['Bounded retrospective case studies; no prospective or clinical validation.',
                                  'Weight perturbations are engineering diagnostics, not validated scientific weights.',
                                  'Ablations compare topology-only and degree-only logistic regression on identical fixed splits.']}
        output = ROOT/'models/evaluation'/('experiments.json' if report['graph']['synthetic'] else 'real-experiments.json')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
        print(json.dumps({'output': str(output), 'cases': len(cases), 'graph': report['graph']}, indent=2))
    finally:
        store.engine.dispose()


if __name__ == '__main__':
    asyncio.run(run())
