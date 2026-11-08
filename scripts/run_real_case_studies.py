"""Acquire, train and analyze three real diseases with isolated model artifacts."""
import asyncio
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.ingestion import BiomedicalIngestor, CASE_IDS
from backend.app.graph import KnowledgeGraph
from backend.app.ml import ModelService
from scripts.run_experiments import run


async def main():
    print('Acquiring official Open Targets and Europe PMC records...',flush=True)
    manifest=await BiomedicalIngestor(ROOT/'data/real').acquire(CASE_IDS)
    dataset=ROOT/'data/real'/manifest['snapshot_id']/'dataset.json'
    (ROOT/'data/real/latest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    os.environ['DATASET_PATH']=str(dataset)
    os.environ['MODEL_DIRECTORY']=str(ROOT/'models/real-checkpoints')
    os.environ['DATABASE_URL']='sqlite:///'+(ROOT/'runtime/real-cases.db').as_posix()
    graph=KnowledgeGraph.load(dataset)
    print(f"Training on {len(graph.entities)} source entities...",flush=True)
    report=ModelService(graph,ROOT/'models/real-checkpoints').train()
    (ROOT/'models/evaluation').mkdir(parents=True,exist_ok=True)
    (ROOT/'models/evaluation/real-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Training complete; executing all three disease workflows...',flush=True)
    await run()


if __name__=='__main__':
    asyncio.run(main())
