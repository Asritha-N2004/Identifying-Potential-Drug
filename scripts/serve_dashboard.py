"""Serve the built dashboard with the verified local databases and real graph."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime/integration-python'))

if __name__=='__main__':
    if not (ROOT/'frontend/dist/index.html').exists():
        raise SystemExit('Build frontend first: cd frontend; pnpm run build')
    from scripts.local_databases import start
    start()
    credentials=json.loads((ROOT/'runtime/local-databases/credentials.json').read_text(encoding='utf-8'))
    os.environ.setdefault('DATABASE_URL','postgresql+psycopg://research:'+credentials['postgres_password']+'@127.0.0.1:55432/research_integration')
    os.environ.setdefault('NEO4J_URI','bolt://127.0.0.1:17687')
    os.environ.setdefault('NEO4J_USERNAME','neo4j')
    os.environ.setdefault('NEO4J_PASSWORD',credentials['neo4j_password'])
    manifest=json.loads((ROOT/'data/real/latest.json').read_text(encoding='utf-8'))
    os.environ.setdefault('DATASET_PATH',str(ROOT/'data/real'/manifest['snapshot_id']/'dataset.json'))
    os.environ.setdefault('MODEL_DIRECTORY',str(ROOT/'models/real-checkpoints'))
    import uvicorn
    uvicorn.run('backend.app.main:app',host='127.0.0.1',port=8000)
