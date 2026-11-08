"""Acquire the three real case-study snapshots from official public APIs."""
import asyncio
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.ingestion import BiomedicalIngestor, CASE_IDS

if __name__ == '__main__':
    manifest=asyncio.run(BiomedicalIngestor(ROOT/'data/real').acquire(CASE_IDS))
    print(json.dumps(manifest,indent=2))
