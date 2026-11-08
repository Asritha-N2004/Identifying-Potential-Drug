# Research methodology

## Objective and scope

This implementation studies a reproducible pipeline for prioritizing missing drug–disease edges in a heterogeneous graph. It establishes software behavior on fictional data. It does not establish therapeutic efficacy, clinical safety, translational plausibility or performance on a biomedical benchmark.

## Data governance

Every imported edge requires provenance, a source identifier, reference, retrieval timestamp, evidence type, license and original description. Schema validation rejects dangling endpoints and duplicate entity IDs. Canonical identity and unambiguous exact synonyms resolve entities; similar names alone never justify merging. The fixture uses only synthetic identifiers. The real Open Targets adapter transforms explicit source IDs, genetic datatype scores, mechanisms and clinical-stage records into separate source-backed graphs. Other lookup responses remain unreviewed raw records. This implementation does not perform biomedical NER or automatic claim/polarity extraction. See [real case-study methodology](real_case_studies.md).

## Learning protocol

Let V denote all typed graph nodes and R the non-indication relation types. Each relation has a separate learnable linear transform in each of two message-passing layers; messages are mean-aggregated per destination and relation, combined with a self transform and ReLU. Each non-indication edge has an explicitly typed inverse. Drug–disease scores use a learned DistMult relation vector and sigmoid transform. These scores are uncalibrated model outputs.

All TREATS relationships are excluded from message passing and graph feature construction. Known positive pairs are deduplicated across provenance records. The complement of known positives supplies sampled unlabeled controls. Distinct sampled pairs are randomly split with label stratification into approximately 60% training, 20% validation and 20% test. Sampling every unknown as a negative is avoided; however, sampled controls still may include undiscovered positives. This is a limitation of the experiment, not resolved PU learning.

The optimizer is Adam (learning rate 0.01, weight decay 0.0001), embedding size 24, full-batch binary cross entropy. Default training requests 60 epochs with a validation-loss patience of 12. Torch and NumPy seeds are fixed to 42. Checkpoints capture weights, graph hash and node IDs. JSON reports capture split pairs, seed, graph version, requested epochs, actual loss history and metrics. Architecture and optimizer choices are fixed in code rather than completely exposed in API configuration.

## Baselines and metrics

Common neighbors, Jaccard, Adamic–Adar, inverse graph distance, endpoint degrees, resource allocation and disease-personalized PageRank form eight structural features. Logistic regression and random forest fit training labels only. Topology-only and degree-only logistic-regression ablations refit on the same split. The simple structural baselines directly score their corresponding feature. Feature engineering sees no indication labels, but all nodes/non-indication graph topology remain visible: this is transductive evaluation.

ROC-AUC and average precision are calculated on the held-out sampled test set. Average precision is used instead of a trapezoidal PR-AUC and is named accordingly. Precision@10, recall@10, hit@10 and reciprocal rank are computed across the single pooled test list, with a stable tie ordering. They are sensitive to the sampled class balance and tie policy, and do not constitute per-query MRR, MAP or filtered knowledge graph evaluation. Confidence intervals and repeated-seed uncertainty are not implemented.

## Agent coordination and ranking

The nine stages consume the same validated graph and trained checkpoint. Disease analysis resolves context; drug knowledge excludes known indications; graph analysis retrieves actual connectivity and centralities; graph ML computes model scores; literature and safety report source availability/gaps; ranking applies explicit weighted components; explanation lists actual paths and limitations; QC checks identifier consistency, bounded scores and provenance. There is no LLM substitution for computation.

Absent evidence scores zero. No publications are invented, duplicated or counted in the fixture. Real-candidate retrieval preserves Europe PMC metadata and openFDA label sections as unreviewed source records, with bounded top-three retrieval and request deadlines. Literature support and pharmacological plausibility remain zero; automated retrieval-to-claim adjudication is outside implemented scope. Contradictory evidence cannot be detected when no annotated evidence dataset exists, and absence of contradiction is never a positive finding.

## Model sensitivity explanations

For each candidate, the explanation stage recomputes its trained-model score after removing each of up to 12 distinct non-indication edges found in the retrieved paths. Forward and inverse message-passing instances are removed together. The signed difference from the original score is recorded with source provenance, and the original tensors remain unchanged. This bounded perturbation explanation measures computational edge sensitivity without retraining. It does not estimate biological causation, treatment effect or a complete faithful subgraph explanation.

## Required validation before scientific claims

Use a versioned, licensed real-world benchmark; audit provenance groups and indirect label proxies; group publication-derived relationships; apply historical cutoff dates to every edge and annotation; evaluate drug/disease cold starts and stratified splits; define experimentally supported negative controls where possible; evaluate per-disease filtered ranking with confidence intervals; tune only against validation data; include independent replication. Current random pair splitting does not satisfy these requirements. Performance on a deterministic synthetic motif must never be described as biomedical discovery or superiority.
