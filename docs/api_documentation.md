# API reference

Interactive generated documentation is served at `/docs` and OpenAPI JSON at `/openapi.json`. Use a single backend worker. All POST routes optionally require `X-API-Key` when `ADMIN_API_KEY` is configured.

| Resource | Routes |
|---|---|
| Health | GET `/api/health` |
| Diseases | GET `/api/diseases`, `/api/diseases/search?q=`, `/api/diseases/{id}`, `/{id}/genes`, `/{id}/pathways` |
| Drugs | GET `/api/drugs`, `/api/drugs/search?q=`, `/api/drugs/{id}`, `/{id}/targets` |
| Graph | GET `/api/graph/statistics`, `/api/graph/neighbors/{id}`, `/api/graph/subgraph/{id}`, `/api/graph/paths?source=&target=` |
| Discovery | POST `/api/repurposing/predict`, `/api/repurposing/rank`, `/api/agents/run` |
| Results | GET `/api/repurposing/results/{job_id}`, `/api/repurposing/candidates/{disease_id}` |
| Agents | GET `/api/agents/status/{job_id}`, `/api/agents/logs/{job_id}` |
| Models | GET `/api/model/info`, `/api/model/metrics`; POST `/api/model/train` |
| Sources | GET `/api/sources`; POST `/api/sources/{source}/search` |

Train body: `{"epochs":60,"seed":42}`. Discovery body: `{"disease_id":"SYNTHETIC:Disease:0","limit":10}`. Optional discovery `weights` must specify exactly `model`, `network`, `literature`, `pharmacology`, and `completeness`, with nonnegative finite values summing to one. Source lookup body: `{"query":"biomedical search term","page":0}`.

Training/discovery return HTTP 202 with `job_id`. Poll agent status until complete or failed, then inspect the persisted `result` or `error`. Discovery requires a matching checkpoint (409 otherwise). Unknown entities/jobs return 404, request validation 422 and source HTTP failures 502. Graph paths are bounded to five paths with no more than five hops. Search results are bounded to 100 loaded entities.

Jobs persist their input, result and status in SQL. Agent logs persist durations and structured execution summaries, not private internal model reasoning. The API currently uses validated input schemas but does not declare dedicated response models on every route; complete response-schema contracts remain a limitation.

Compatibility routes added on 8 November 2026: POST `/api/predictions/run`, GET `/api/predictions/{id}`, GET `/api/predictions/{id}/candidates`, GET `/api/predictions/{id}/explanations`, GET `/api/models/metrics`, POST `/api/models/train`, GET `/api/graph/neighborhood/{id}` and GET `/api/graph/path?source=&target=`. Candidate and explanation routes require a completed discovery job (409 otherwise) and return the evidence-bearing candidate list. Disease/drug search accepts `offset>=0` and `1<=limit<=100`; queries are capped at 300 characters. Graph statistics now include entity/relationship distributions, label-free degree distribution, components, isolates and source-provenance coverage.

POST `/api/data/ingest` accepts `{}` for the three default real diseases, or `{"disease_ids":["MONDO_0008383"],"target_limit":100,"drugs_per_disease":20}`. It returns 202 and a `job_id`; poll `/api/agents/status/{job_id}`. A completed result includes the content-addressed `snapshot_id`, source timestamps, counts and limitations. Failed acquisition preserves the active graph. Requests allow at most three distinct MONDO/EFO/Orphanet IDs, 10–200 targets and 1–30 approved drugs per disease.

POST `/api/graph/build` accepts `{"snapshot_id":"<64 lowercase hexadecimal characters>"}`. It verifies the raw-record hash, reconstructs and validates the graph from source envelopes, synchronizes configured stores and replaces the active in-memory graph under the model lock. A previous checkpoint is usable only if its graph hash matches. Missing snapshots return 404; invalid input or snapshot validation returns 422. The selected snapshot persists across restart in `runtime/active-dataset.json`; `DATASET_PATH` explicitly overrides startup selection. SQL/Neo4j synchronization is not a distributed transaction or historical deletion reconciliation.

POST `/api/models/evaluate` recomputes the trained R-GCN's predictions on its saved original test pairs, verifies split disjointness and returns measured metrics, per-disease summaries, pair-level scores and limitations. It does not retrain, resplit or evaluate a fresh external dataset. It returns 409 without a matching checkpoint. Baseline comparisons remain in GET `/api/models/metrics` from the training run. The evaluation CLI reads that original report.
