"""Normalize curated graph JSON and preserve explicit identifier mapping audit."""
import argparse,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.schemas import Dataset
from backend.app.preprocessing import IdentifierMapping,normalize_dataset

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--mappings',type=Path)
    args=parser.parse_args()
    source=Dataset.model_validate_json(args.input.read_text(encoding='utf-8'))
    mappings=[IdentifierMapping.model_validate(m) for m in json.loads(args.mappings.read_text())] if args.mappings else []
    result=normalize_dataset(source,mappings)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2),encoding='utf-8')
    print(f'Validated {len(result.entities)} entities and {len(result.relationships)} relationships')
