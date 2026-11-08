# Real biomedical ingestion and disease case studies

The real workflow uses retrieved Open Targets and Europe PMC records. It is a bounded retrospective research exercise, not a clinically validated discovery system. Raw source responses, retrieval timestamps, source identifiers and terms reminders are preserved. The synthetic fixture remains separate and is used for automated software tests.

## Disease selection

| Disease | Current source ID | Selection rationale |
|---|---|---|
| Rheumatoid arthritis | MONDO_0008383 | Immune-mediated disease with retrievable genetic associations and drug mechanisms |
| Psoriasis | MONDO_0005083 | Immune-mediated disease with overlap suitable for cross-disease graph exploration |
| Inflammatory bowel disease | MONDO_0005265 | Broader disease concept that exposes ontology/granularity limitations alongside immune-pathway overlap |

These canonical IDs and names were resolved through the official Open Targets search API on 8 November 2026. The rationale describes experimental design, not an inference that a shared pathway implies an effective treatment. The IBD umbrella has few directly recorded approved indications in this snapshot; child-disease approvals are not silently propagated to it.

## Acquisition and transformation

For each disease the adapter requests the first 100 aggregate-ranked direct target associations, then retains a gene–disease edge only when the genetic-association datatype score is positive. It never uses the aggregate score as independent genetic evidence. Up to 20 source-approved drugs per disease are selected deterministically by ChEMBL ID; drug mechanisms are fetched separately. This limits download size but creates selection bias and misses potentially useful drugs outside the subset.

Protein mapping uses explicit UniProt Swiss-Prot references. Pathway membership uses supplied Reactome IDs. Gene identifiers remain Ensembl IDs; no fuzzy symbol mapping or inferred MONDO merge occurs. `APPROVAL` clinical-stage assertions create TREATS labels; other source clinical stages create INVESTIGATED_IN records. Source assertions do not establish jurisdiction-specific current regulatory approval. Historical, discontinued and formulation-specific statuses require further review.

Each disease also receives a bounded Europe PMC search. Up to five available PubMed-indexed hits within the first 25 search results are retained as context metadata. Publication nodes remain disconnected: search co-occurrence is not evidence of efficacy, target engagement, or experimental study findings. Candidate agents separately retrieve bounded drug–disease search hits and openFDA label sections for review. These unadjudicated records contribute zero literature/pharmacology support to ranking.

Snapshots live in `data/real/<raw-sha256>/`: `raw.json`, `dataset.json` and `manifest.json`. `data/real/latest.json` identifies the latest CLI acquisition. Cache flags are excluded from hashes; original retrieval timestamps are retained. A cache hit reproduces the same raw snapshot. The model/report graph hash additionally identifies the normalized graph. Restricted DrugBank, DisGeNET and KEGG resources are not accessed.

## Evaluation and leakage controls

The positive label is a distinct source-approved drug–disease pair in this selected subset. Unlabeled controls are sampled without replacement from pairs with no recorded clinical stage. Approved and investigational clinical edges are removed from graph message passing, path features and structural baselines. Both kinds of clinical pairs are excluded from candidate discovery and control sampling. Publication context nodes are excluded from R-GCN embeddings and message passing, so adding unrelated publication metadata does not change the predictive graph.

The fixed seed is 42. The experiment uses a stratified random pair split, validation-loss early stopping, then an original held-out test evaluation. Source/record duplicates are deduplicated before splitting. Disease-level summaries are reported alongside pooled metrics; a disease with only one test class has undefined ROC-AUC, reported as null. Average precision is not trapezoidal PR-AUC. Pooled reciprocal rank/hit metrics are not per-disease full-catalog MRR/Hits@K.

This protocol is transductive and selection-biased. Genetic datatype scores exclude direct known-drug support, but aggregate-ranked target selection can still encode clinical ascertainment. Approval-based drug selection and correlated upstream sources remain additional biases. There is no temporal or cold-start validation, causal inference, calibrated efficacy probability, or external replication. Weak or undefined disease-specific results must not be hidden by a stronger pooled score.

## Reproduction

From the repository root:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
python scripts/run_real_case_studies.py
python scripts/verify_real_api.py
python -m pytest -q
```

The first command acquires source records, trains an isolated checkpoint under `models/real-checkpoints`, and runs all three nine-stage agent workflows. It writes `models/evaluation/real-evaluation.json` and `real-experiments.json`, including path provenance, candidate evidence gaps, single-edge occlusion and weight sensitivity. API verification exercises ingestion, graph activation, reevaluation and disease/pathway retrieval against the real snapshot. It activates the graph locally and writes `runtime/real-api-verification.json`.

To serve the saved dataset/checkpoint explicitly:

```powershell
$snapshot = Get-Content data/real/latest.json -Raw | ConvertFrom-Json
$env:DATASET_PATH = (Resolve-Path "data/real/$($snapshot.snapshot_id)/dataset.json").Path
$env:MODEL_DIRECTORY = (Join-Path (Get-Location) 'models/real-checkpoints')
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Alternatively, use the dashboard's **Data sources → Ingest three diseases → Build and activate graph**, then **Train model**. Network failures produce explicit failed jobs or evidence-unavailable statuses; no replacement facts or model metrics are generated. The downloaded snapshot can be served offline; candidate evidence lookups may return cached results or explicit availability gaps.

See [measured real results](real_results.md), [API contracts](api_documentation.md), [source/terms details](data_sources.md) and [remaining limitations](limitations.md).
