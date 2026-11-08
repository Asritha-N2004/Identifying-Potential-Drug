# Measured real-source results — 8 November 2026

These measurements describe a small retrospective, selection-biased benchmark. They are not evidence of therapeutic effectiveness.

Snapshot: `825e1fa8db75db2893ebe93bfc7445bab0b5c6e13ee861489d1bfa1a20300e5c`. Graph SHA-256: `424006a5efc2df196f73f0afb74a7db706dc9d4019a2324151ef6cd33cba9f38`.

Graph: 1054 entities, 1639 relationships, 18 label-free connected components and 16 isolated nodes. Source-provenance coverage: 100%. This measures source presence, not evidence quality.

| Entity type | Count |
|---|---:|
| Disease | 3 |
| Gene | 224 |
| Protein | 223 |
| Pathway | 552 |
| Drug | 40 |
| Publication | 12 |

Seed 42; 55 training / 18 validation / 19 test pairs. Unknown controls are unlabeled. All clinical edges and publication context are excluded from the R-GCN predictive graph.

| Model | ROC-AUC | Average precision | Precision@10 | Recall@10 |
|---|---:|---:|---:|---:|
| R-GCN | 0.8667 | 0.9023 | 0.8000 | 0.8889 |
| Logistic regression | 0.7500 | 0.6808 | 0.8000 | 0.8889 |
| Random forest | 0.9389 | 0.9419 | 0.8000 | 0.8889 |
| Common neighbors | 0.5556 | 0.5322 | 0.6000 | 0.6667 |
| Jaccard | 0.5556 | 0.5322 | 0.6000 | 0.6667 |
| Adamic-Adar | 0.5556 | 0.5322 | 0.6000 | 0.6667 |
| Resource allocation | 0.5556 | 0.5322 | 0.6000 | 0.6667 |
| Personalized PageRank | 0.3778 | 0.4955 | 0.3000 | 0.3333 |
| Logistic regression: topology only | 0.3889 | 0.5511 | 0.3000 | 0.3333 |
| Logistic regression: degree only | 0.7389 | 0.6952 | 0.8000 | 0.8889 |

## Disease-specific held-out results

| Disease | Test pairs | Positive labels | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|
| psoriasis | 5 | 3 | 1.0000 | 1.0000 |
| inflammatory bowel disease | 9 | 1 | 0.1250 | 0.1250 |
| rheumatoid arthritis | 5 | 5 | Undefined (one test class) | 1.0000 |

The disease samples are too small and imbalanced to support generalization claims. An all-positive disease test subset cannot measure discrimination, even when average precision is one. No model-superiority or clinical-efficacy claim follows from the pooled table.

## Executed candidate workflows

| Disease | Computed candidates | Candidates with paths | Unreviewed candidate search hits | Maximum sensitivity rank shift |
|---|---:|---:|---:|---:|
| psoriasis | 16 | 14 | 1 | 0 |
| inflammatory bowel disease | 31 | 28 | 4 | 0 |
| rheumatoid arthritis | 11 | 7 | 4 | 0 |

All nine stages completed for every disease. Weight diagnostics perturb each of five components by ±20%, renormalize and rerank; these are engineering sensitivity checks, not scientifically validated weights. Search hits are unreviewed and may duplicate publications across candidates. They are not counts of independent supporting experiments. Candidates without paths explicitly lack graph-path support. Full candidate identities and evidence remain in `models/evaluation/real-experiments.json`; none is presented here as a treatment recommendation.

The fixed snapshot and final model configuration are reported without selecting the best intermediate run. Candidate evidence availability can vary with upstream availability and cache state. Raw source timestamps and retrieval statuses are retained.

Verification for the real-data milestone: 21 backend tests passed; two external-database tests skipped at that stage. Five frontend tests, TypeScript validation and the Vite production build passed. Real-snapshot API verification passed. See [later deployment results](deployment_results.md) for live database verification and current Docker status.

Reproduce with `python scripts/run_real_case_studies.py`, then `python scripts/verify_real_api.py` and `python scripts/write_real_report.py`. See [methodology and limitations](real_case_studies.md).
