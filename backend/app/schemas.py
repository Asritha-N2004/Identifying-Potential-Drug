"""Validated graph, request and provenance contracts."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Entity(BaseModel):
    id: str
    name: str
    kind: Literal['Drug','Disease','Gene','Protein','Pathway','BiologicalProcess','MolecularFunction','CellularComponent','Publication','ClinicalTrial']
    synonyms: list[str] = Field(default_factory=list)
    synthetic: bool = False
    attributes: dict = Field(default_factory=dict)

class Provenance(BaseModel):
    source: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    retrieved_at: datetime
    evidence_type: str
    license: str = Field(min_length=1)
    synthetic: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)

class Relationship(BaseModel):
    source: str
    target: str
    relation: Literal['TREATS','TARGETS','ENCODED_BY','ASSOCIATED_WITH','PARTICIPATES_IN','INTERACTS_WITH','INHIBITS','ACTIVATES','REGULATES','SUPPORTED_BY','INVESTIGATED_IN','BELONGS_TO','EXPRESSED_IN']
    provenance: Provenance
    description: str = Field(min_length=1)
    directed: bool = True

class Dataset(BaseModel):
    version: str
    entities: list[Entity]
    relationships: list[Relationship]

    @model_validator(mode='after')
    def validate_references(self):
        ids = {e.id for e in self.entities}
        entities={e.id:e for e in self.entities}
        if len(ids) != len(self.entities):
            raise ValueError('Duplicate canonical identifiers')
        for edge in self.relationships:
            if edge.source not in ids or edge.target not in ids or edge.source == edge.target:
                raise ValueError('Invalid relationship endpoint')
            if edge.relation in {'TREATS','INVESTIGATED_IN'} and (entities[edge.source].kind!='Drug' or entities[edge.target].kind!='Disease'):
                raise ValueError('Clinical relationships must connect Drug to Disease')
            if edge.provenance.synthetic != entities[edge.source].synthetic or edge.provenance.synthetic != entities[edge.target].synthetic:
                raise ValueError('Synthetic and real relationships must remain in separate datasets')
        return self

class PredictRequest(BaseModel):
    disease_id: str
    limit: int = Field(default=10, ge=1, le=100)
    weights: dict[str, float] = Field(default_factory=lambda: {'model':.35,'network':.25,'literature':.2,'pharmacology':.1,'completeness':.1})

    @model_validator(mode='after')
    def validate_weights(self):
        if set(self.weights) != {'model','network','literature','pharmacology','completeness'}:
            raise ValueError('Exactly five documented score components required')
        if any(not 0 <= v <= 1 for v in self.weights.values()) or abs(sum(self.weights.values())-1)>1e-6:
            raise ValueError('Weights must be finite, nonnegative and sum to one')
        return self

class TrainRequest(BaseModel):
    epochs: int = Field(default=60, ge=1, le=500)
    seed: int = 42

class IngestRequest(BaseModel):
    disease_ids: list[str] = Field(default_factory=lambda:['MONDO_0008383','MONDO_0005083','MONDO_0005265'],min_length=1,max_length=3)
    target_limit: int = Field(default=100,ge=10,le=200)
    drugs_per_disease: int = Field(default=20,ge=1,le=30)

    @model_validator(mode='after')
    def identifiers(self):
        import re
        if len(set(self.disease_ids))!=len(self.disease_ids) or any(not re.fullmatch(r'(MONDO|EFO|Orphanet)_[0-9]+',i) for i in self.disease_ids):
            raise ValueError('Distinct supported ontology identifiers required')
        return self

class BuildRequest(BaseModel):
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{64}$')
