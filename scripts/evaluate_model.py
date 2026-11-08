"""Inspect an existing measured evaluation; never silently retrain a model."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    directory = Path(os.getenv('MODEL_DIRECTORY', ROOT / 'models/checkpoints'))
    path = directory / 'evaluation.json'
    if not path.exists():
        raise SystemExit('No evaluation found. Run python scripts/train_model.py first.')
    report = json.loads(path.read_text(encoding='utf-8'))
    print(json.dumps({key: report[key] for key in ['graph_sha256', 'synthetic', 'seed', 'split', 'metrics', 'limitations']}, indent=2))
