# Acceptance status

This matrix intentionally distinguishes implementation from observed verification. It does not certify the full master prompt as complete.

| Requirement | Status |
|---|---|
| Backend starts | Verified locally with Uvicorn |
| Frontend compiles | TypeScript and Vite production build passed |
| Neo4j integration | Verified against native Community 5.26.33, including provenance, idempotency and restart persistence |
| PostgreSQL integration | Verified against native 16.15, including graph/job/log persistence and restart |
| Public connectors | All nine retrieved live JSON envelopes; mocked regression tests; partial schema/pagination support |
| Preprocessing | Schema validation, exact resolution, namespace normalization, audited mappings, deduplication and bounded Open Targets ETL; no bulk mirror |
| Knowledge graph / actual-record queries | Verified on fixtures and real Open Targets/Europe PMC records |
| Graph features | Paths, degree, betweenness, PageRank and structural baseline features |
| Baseline prediction | Logistic regression, random forest and three structural baselines measured |
| Heterogeneous graph model | Relation-aware R-GCN/DistMult with typed graph and inverse relations |
| Training / evaluation | Working random split, validation selection, checkpoints and measured report |
| Candidate inference / ranking | Working fixture workflow with known-indication exclusion |
| Multi-agent orchestration | Nine stages, persisted execution summaries and errors |
| Literature retrieval | Metadata lookup integrated for bounded real candidates; claim adjudication absent |
| Safety retrieval | openFDA label-section retrieval integrated for bounded real candidates; clinical validation absent |
| Explainability | Actual path provenance, score components and trained-model edge-occlusion sensitivity; no GNNExplainer |
| Provenance | Validated and retained in graph/SQL/results |
| Dashboard | Backend-connected seven-view React UI with Cytoscape and measured charts |
| Automated tests | 24 backend tests passed with live services, zero skipped; earlier five frontend tests passed |
| Docker Compose | Deployment and isolated-test configurations validate; image build/container execution pending missing Docker engine/WSL |
| Installation / methodology documentation | Included |
| Offline demo | Synthetic training and inference implemented; no external credentials required |
| Synthetic labeling / research labeling | Present in dataset, dashboard, results and evaluation |
| Real disease case studies | Three retrospective workflows executed; source records and measured reports saved |
| Ingestion/build/evaluation endpoints | Implemented and verified with mocked tests and the real saved snapshot |
| Real biomedical discovery | No experimentally or clinically validated repurposing discovery established |
