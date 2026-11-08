"""Conservative canonical identifier normalization with explicit mapping audit."""
import re
from pydantic import BaseModel,Field
from .schemas import Dataset

class IdentifierMapping(BaseModel):
    original: str
    canonical: str
    source: str=Field(min_length=1)
    confidence: float=Field(ge=0,le=1)
    reference: str=Field(min_length=1)

def canonical_identifier(value:str)->str:
    """Normalize recognized syntactic namespaces; never equate entities by name."""
    value=value.strip()
    if value.startswith('SYNTHETIC:'):return value
    if re.fullmatch(r'CHEMBL\d+',value,re.I):return value.upper()
    if re.fullmatch(r'ENSG\d{11}',value,re.I):return value.upper()
    match=re.fullmatch(r'(MONDO|DOID)[_:](\d+)',value,re.I)
    if match:return f'{match[1].upper()}:{match[2]}'
    match=re.fullmatch(r'(pubchem|ncbi_gene)[:](\d+)',value,re.I)
    if match:return f'{match[1].lower()}:{int(match[2])}'
    # Unknown IDs are preserved for explicit curator review, not guessed.
    return value

def normalize_dataset(dataset:Dataset,mappings:list[IdentifierMapping]|None=None):
    mappings=mappings or []
    by_original={m.original:m.canonical for m in mappings}
    if len(by_original)!=len(mappings):raise ValueError('Duplicate mapping source identifiers')
    ids={e.id:canonical_identifier(by_original.get(e.id,e.id)) for e in dataset.entities}
    if len(set(ids.values()))!=len(ids):raise ValueError('Many-to-one entity merge requires manual resolution')
    data=dataset.model_dump(mode='json')
    for entity in data['entities']:
        original=entity['id'];entity['id']=ids[original]
        entity['synonyms']=list(dict.fromkeys(s.strip() for s in entity['synonyms'] if s.strip()))
        audit=[m.model_dump() for m in mappings if m.original==original]
        entity['attributes']['identifier_mapping_audit']=audit
    seen=set();clean=[]
    for edge in data['relationships']:
        edge['source']=ids[edge['source']];edge['target']=ids[edge['target']]
        key=(edge['source'],edge['target'],edge['relation'],edge['provenance']['source'],edge['provenance']['record_id'])
        if key not in seen:clean.append(edge);seen.add(key)
    data['relationships']=clean
    return Dataset.model_validate(data)
