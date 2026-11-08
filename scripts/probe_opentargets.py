"""Inspect official GraphQL schema for ingestion adapter development."""
import json
from pathlib import Path
import httpx

if __name__ == '__main__':
    query = '''{__schema{types{name fields{name args{name type{kind name ofType{kind name}}} type{kind name ofType{kind name}}}}}}'''
    response = httpx.post('https://api.platform.opentargets.org/api/v4/graphql', json={'query': query}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    Path('runtime/opentargets-schema.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    for obj in payload.get('data', {}).get('__schema', {}).get('types', []):
        if obj['name'] in ['Disease', 'KnownDrugs', 'KnownDrug', 'Target', 'Drug', 'AssociatedTargets', 'Association', 'MechanismsOfAction', 'Indications']:
            print(json.dumps(obj))
