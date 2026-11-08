"""Train and write measured fixture evaluation results from repository root."""
import sys
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.graph import KnowledgeGraph
from backend.app.ml import ModelService

if __name__=='__main__':
    graph=KnowledgeGraph.load(Path(os.getenv('DATASET_PATH',ROOT/'data/sample/synthetic.json')))
    report=ModelService(graph,Path(os.getenv('MODEL_DIRECTORY',ROOT/'models/checkpoints'))).train()
    output=ROOT/'models/evaluation'/('synthetic-evaluation.json' if report['synthetic'] else 'real-evaluation.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    import json
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:{m:v for m,v in values.items() if m not in ['roc','pr']} for k,values in report['metrics'].items()},indent=2))
