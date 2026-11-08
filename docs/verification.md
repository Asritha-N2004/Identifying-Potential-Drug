# Verification record

Latest database milestone: **24 backend tests passed, zero skipped**, including three live PostgreSQL/Neo4j integration tests. Native real-data HTTP workflow and application/database restart persistence also passed. Docker Compose configuration validation passed; container startup is pending a Docker engine/WSL installation. See [deployment results](deployment_results.md). Earlier sections below retain historical verification counts.

Verified on Windows with Python 3.12.10, Torch 2.13.0 CPU, Node 24.22.1 and pnpm 11.25.0. External-service checks were performed on 8 November 2026 (Asia/Calcutta). Backend packages came from the existing local Python environment; install requirements in an isolated environment for reproduction.

| Check | Observed result |
|---|---|
| Python backend regression suite | 16 passed; 2 optional database tests skipped |
| React/Vitest suite | 3 passed |
| TypeScript type checking | Passed |
| Vite production build | Passed; large-bundle optimization warning |
| Native API startup | Uvicorn startup complete |
| API health request | HTTP 200, SQLite, synthetic mode, matching trained checkpoint |
| Compiled dashboard HTTP request | HTTP 200 |
| Offline CLI workflow | Complete, 10 ranked synthetic candidates including edge-occlusion explanations, result saved under runtime |
| Nine public source lookup clients | All retrieved JSON envelopes, including Europe PMC and openFDA |
| Docker Compose | Parsed YAML; runtime unavailable, startup not verified |
| PostgreSQL / Neo4j | Optional live tests skipped; services not available |
| Browser visual inspection | Blocked: browser automation inventory empty |

The source smoke-check report is [source-verification.json](source-verification.json). It records URLs and timestamps, not scientific conclusions. Complete raw responses remain local under `runtime/source-checks/`, outside Git. The smoke check found and led to a fix for Windows encoding of Greek letters, non-breaking hyphens and mathematical symbols in source cache files. A mocked Unicode round-trip regression test covers this behavior.

Commands used for verification (from repository root unless noted):

```text
python scripts/make_sample.py
python -m pytest -q
python scripts/train_model.py
python scripts/run_demo.py
python scripts/verify_sources.py
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend checks invoked installed command entry points directly because npm was unavailable on PATH:

```text
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
node node_modules/vitest/vitest.mjs run --pool=threads --maxWorkers=1
```

The latter commands run in `frontend`. Vitest workers and Python asyncio required execution outside the restricted Windows sandbox. Initial test failures from temporary directory setup, an incorrect fixture node assertion and a test syntax error were corrected before the passing suite. No test failures are represented as successes.

The deterministic seed-42 experiment requested 60 epochs, used validation early stopping, and held out 20 sampled pairs. [The measured report](../models/evaluation/synthetic-evaluation.json) retains actual loss history and all split pairs.

| Model | Test ROC-AUC | Test average precision |
|---|---:|---:|
| R-GCN + DistMult | 0.410 | 0.561 |
| Logistic regression | 1.000 | 1.000 |
| Random forest | 1.000 | 1.000 |
| Common neighbors | 0.500 | 0.500 |
| Jaccard | 0.500 | 0.500 |
| Adamic–Adar | 0.500 | 0.500 |
| Resource allocation | 0.500 | 0.500 |
| Personalized PageRank | 1.000 | 1.000 |
| Logistic regression: topology only | 1.000 | 1.000 |
| Logistic regression: degree only | 0.500 | 0.500 |

These final results use `synthetic-v2`: 72 entities and 152 edges, with fictional protein interaction links connecting the previous four modules. Earlier measurements on `synthetic-v1` are superseded. Candidate path availability and nonempty edge-occlusion output are now asserted in the end-to-end test. The results remain based on a tiny fictional motif and sampled unlabeled controls. The baseline advantage must be preserved; no neural-model superiority or biomedical efficacy conclusion follows.
# Latest real-data milestone

The real-data continuation passed 21 backend tests and five frontend tests, with two external-database tests skipped. TypeScript validation and the production build passed. Ingestion, graph activation and reevaluation were also exercised on the downloaded real snapshot. Three real disease workflows completed. See [real-source results](real_results.md) and [reproduction](real_case_studies.md). The earlier synthetic verification in this file remains historical evidence for the fixture workflow.
