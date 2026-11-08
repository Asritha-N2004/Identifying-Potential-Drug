import pytest
from pathlib import Path
from backend.app.schemas import Dataset
from backend.app.preprocessing import canonical_identifier,normalize_dataset,IdentifierMapping

def test_canonical_namespace_without_fuzzy_equivalence():
    assert canonical_identifier(' mondo_0004975 ')=='MONDO:0004975'
    assert canonical_identifier('chembl123')=='CHEMBL123'
    assert canonical_identifier('unrecognized name')=='unrecognized name'

def test_dedupe_preserves_mapping_audit():
    dataset=Dataset.model_validate_json(Path('data/sample/synthetic.json').read_text())
    dataset.relationships.append(dataset.relationships[0])
    clean=normalize_dataset(dataset)
    assert len(clean.relationships)==len(dataset.relationships)-1
    assert 'identifier_mapping_audit' in clean.entities[0].attributes

def test_many_to_one_mapping_rejected():
    dataset=Dataset.model_validate_json(Path('data/sample/synthetic.json').read_text())
    first,second=dataset.entities[:2]
    mapping=IdentifierMapping(original=first.id,canonical=second.id,source='test-only',confidence=1,reference='fixture://mapping')
    with pytest.raises(ValueError):normalize_dataset(dataset,[mapping])
