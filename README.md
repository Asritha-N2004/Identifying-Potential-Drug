# A Graph-Based Multi-Agent Framework for Identifying Potential Drug Repurposing Candidates

Atlas is a local research workbench combining a provenance-preserving knowledge graph, trained relational graph neural network, baseline comparisons, nine deterministic agent stages, ranked hypotheses, and an interactive React dashboard.

A protected published-results edition is available at [atlas-drug-repurposing.vercel.app](https://atlas-drug-repurposing.vercel.app/). Sign-in details are saved locally in `runtime/cloud-auth/login.txt`. See [Vercel deployment and login verification](docs/vercel_deployment.md). The cloud edition serves the saved real-disease analyses; new ingestion and model training remain in the full Python application.

New users can select **Create account** on the deployed login page. Registration uses private persistent Vercel storage and preserves the existing accounts.

**Current status:** functional synthetic offline workflow, public-source lookup clients, real Open Targets/Europe PMC ingestion and three executed real disease case studies. This is a research implementation; efficacy, safety and generalization have not been validated. See [real case studies](docs/real_case_studies.md), [measured real results](docs/real_results.md), [acceptance status](docs/acceptance.md) and [earlier verification results](docs/verification.md).

## Research scope

The research question is whether graph connectivity and learned multirelational representations can help prioritize unknown drug–disease pairs for further investigation. The application separates retrieved records, graph connectivity, model scores, and clinical evidence. No LLM is required. Scores are computational priorities, never clinical probabilities or prescribing recommendations.

The supplied dataset contains **72 wholly fictional entities**: 24 drugs, 8 diseases, 16 genes, 16 proteins, 4 pathways and 4 biological processes. All identifiers begin `SYNTHETIC:` and all relationships have synthetic provenance. They deliberately avoid real drug or disease names. No fixture record represents a real publication, clinical trial, indication or biological finding.

## Quick start: native Python

Run these commands from the repository root with Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python scripts/train_model.py
python scripts/run_demo.py
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The CLI demo writes a complete auditable result to `runtime/demo-result.json`. Training writes `models/checkpoints/rgcn.pt` and `models/checkpoints/evaluation.json`, and the training script also writes a shareable report under `models/evaluation/`. Checkpoints are ignored by Git and rebuilt locally.

Install Node 22+ and npm, then in a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [the development dashboard](http://localhost:5173). Vite forwards API calls to port 8000. Alternatively, run `npm run build` in `frontend` **before starting the backend**; FastAPI then serves the compiled dashboard at [localhost:8000](http://localhost:8000). The frontend requires no remote LLM, credentials or data source for the demo. Fonts use a web font with a system fallback.

If npm is unavailable but pnpm is installed, `pnpm install`, `pnpm build`, and `pnpm dev` are equivalent. On the original execution machine pnpm was bundled outside PATH. Dependency installation required elevated execution because the Windows sandbox blocks symlink creation and network access. Local runtime operations also required network permission for asyncio loopback sockets.

## Docker deployment

Install Docker Engine / Docker Desktop with Compose v2 or later:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open [the dashboard](http://localhost:8080), click **Train model**, then select a synthetic disease and **Run discovery**. Compose starts PostgreSQL, Neo4j, the API and Nginx with persistent volumes, health checks and dependencies. The backend validates and imports the fixture into SQL and Neo4j at startup. It does not train automatically.

Demo password defaults are only for local development. For a deployed environment set strong database passwords and `ADMIN_API_KEY`, use TLS at a reverse proxy, and retain private network access. The UI's Data sources page accepts the optional API key for POST requests in the current browser session. This is a local single-user application; user accounts and multi-tenant authorization are not implemented. Native PostgreSQL/Neo4j integration is now verified: all 24 backend tests passed with no skips, including three live integration tests. Both Compose files validate, but container startup remains pending because this host has no Docker engine/WSL. See [verified deployment results](docs/deployment_results.md) and [setup/reproduction](docs/deployment.md).

Stop containers with `docker compose down`. Volumes persist unless explicitly removed. Do not use `down -v` if you need the stored jobs or models.

## Architecture

```mermaid
flowchart TD
  A[Public source clients] --> B[Timestamped raw response cache]
  B --> C[Human-reviewed canonical Dataset JSON]
  D[Labeled synthetic fixture] --> E[Schema and identifier validation]
  C --> E
  E --> F[NetworkX multirelational graph]
  E --> G[SQL metadata and Neo4j adapter]
  F --> H[Label-free message-passing graph]
  H --> I[R-GCN with DistMult decoder]
  H --> J[Structural baselines]
  I --> K[Checkpoint and measured evaluation]
  K --> L[Nine-stage deterministic orchestrator]
  F --> L
  L --> M[Component scoring, provenance QC and paths]
  M --> N[FastAPI jobs and audit summaries]
  N --> O[React dashboard and JSON export]
```

Implementation modules are intentionally grouped by responsibility rather than generating empty files for every proposed module. See [architecture](docs/architecture.md), [methodology](docs/methodology.md), [source documentation](docs/data_sources.md), [API](docs/api_documentation.md), and [limitations](docs/limitations.md).

## Workflow

1. Validate/import the loaded graph and inspect its provenance.
2. Train a checkpoint and compare measured baseline results. An untrained or mismatched checkpoint cannot run discovery.
3. Select one of the loaded diseases. Exact canonical identifiers or unambiguous exact synonyms are accepted; no fuzzy entity merges occur.
4. The agent pipeline resolves disease context, excludes known indications, retrieves graph paths, scores candidate pairs, records literature and safety gaps, computes configurable ranking components, explains paths, and validates provenance.
5. Inspect the candidate table, path edge directions, agent summaries and model curves. Export the actual result JSON.

The literature and safety agents explicitly report missing evidence in the fixture. For a real curated graph, they retrieve Europe PMC metadata and openFDA label sections for up to three highest-model-score candidates, with bounded timeouts and no positive support score until human adjudication. Public-source lookup is also available separately under Data sources. Search hits and label text do not automatically become supportive or contradictory claims.

## Graph and data import

Run `python scripts/run_real_case_studies.py` for real acquisition, isolated model training and all three disease workflows. Run `python scripts/verify_real_api.py` to verify ingestion, graph activation and reevaluation through the actual API, then `python scripts/write_real_report.py` to regenerate the measured Markdown report. The dashboard also provides ingestion/activation controls under **Data sources**. See [reproduction and source-selection details](docs/real_case_studies.md).

`backend/app/schemas.py` defines the JSON contract. Each entity has an immutable canonical identifier, type, name, synonyms and synthetic flag. Each relationship stores source and target, a controlled relation type, directionality, original description and provenance (source, record ID, reference, retrieval timestamp, evidence type, license and optional source confidence).

Prepare a human-curated real dataset in this contract, keeping it separate from synthetic data. Optional preprocessing normalizes recognized identifier syntax and retains mapping confidence/provenance. It rejects implicit many-to-one merges:

```powershell
python scripts/build_graph.py data/processed/curated.json
$env:DATASET_PATH="data/processed/curated.json"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Train a new checkpoint through the dashboard after changing datasets. The model stores the exact graph SHA-256 and node mapping; inference rejects incompatible checkpoint state. Open Targets ETL transforms explicit source IDs into the validated schema; other lookup-client responses remain unreviewed raw records. General fuzzy cross-database alignment and evidence-claim adjudication are absent. Restricted databases are not accessed.

Additional data commands:

```powershell
python scripts/download_data.py europe_pmc "a real biomedical query" --output data/raw/search.json
python scripts/preprocess_data.py data/processed/input.json data/processed/normalized.json
```

Optional `--mappings mappings.json` supplies an array of `{original, canonical, source, confidence, reference}` objects; it does not authorize fuzzy name matching.

Native PostgreSQL uses `DATABASE_URL=postgresql+psycopg://user:password@host:5432/database`. Native Neo4j uses `NEO4J_URI`, `NEO4J_USERNAME` and `NEO4J_PASSWORD`. Without these the demo uses SQLite plus NetworkX. Local Python reads shell environment variables; it does not automatically load `.env`. Neo4j stores typed entities and `BIOMEDICAL` edges with relation properties and full provenance JSON. SQL stores entities, relationships, jobs and agent executions. Database schema migrations and Neo4j-backed query serving are not implemented.

## Models and ranking

Training uses a two-layer PyTorch R-GCN with inverse types for nonclinical edges, learned node embeddings and a DistMult decoder. It excludes **all** `TREATS` and `INVESTIGATED_IN` edges from message passing, path-derived features and baseline features. Publication-context nodes are excluded from model embeddings. Positive pairs are deduplicated before a stratified approximately 60/20/20 random pair split. Equally many distinct unknown pairs without recorded clinical stages are sampled without replacement as unlabeled controls. This is a sampled classification experiment, **not** formal positive-unlabeled learning or a set of biologically confirmed negatives.

Validation loss selects an early-stopped checkpoint. Baselines include logistic regression, random forest, common neighbors, Jaccard, Adamic–Adar, Resource Allocation and Personalized PageRank, plus topology/degree feature ablations. Reports contain measured loss curves, ROC-AUC, average precision, precision/recall/hit at 10 and reciprocal rank on the pooled sampled test set. Reevaluation adds disease-specific ROC-AUC/average-precision summaries with undefined metrics reported explicitly. These remain sampled-pair summaries rather than full-catalog retrieval metrics. No biomedical superiority claim is justified. Temporal, cold-start and disease-stratified split protocols are not implemented.

Default ranking is `0.35 model + 0.25 network + 0.20 literature + 0.10 pharmacology + 0.10 completeness`. Input components are bounded to [0,1]. Model sigmoid output is uncalibrated; network support is inverse shortest retrieved path length, not biological plausibility. Completeness measures presence of path provenance, not sufficiency of medical evidence. Missing literature and pharmacology score zero and weights are never renormalized around missing data. The prediction API accepts all five weights, which must be finite, nonnegative and sum to one.

Explanations include actual path provenance, score components and trained-model single-edge occlusion: the backend removes each of up to 12 path edges and its inverse, recomputes the candidate score, and reports signed sensitivity. This measures the model's response without establishing a biological causal effect. CPU threads default to one for the small fixture; `ML_NUM_THREADS` can override this for a larger deployment.

## Tests

The latest incremental work adds Resource Allocation and disease-personalized PageRank baselines, topology/degree feature ablations, graph quality statistics, paginated search, prediction API aliases and three synthetic case studies with ranking weight sensitivity. See [measured experimental results](docs/experimental_results.md). Run `python scripts/evaluate_model.py` to inspect the saved measured test report and `python scripts/run_experiments.py` after training to reproduce the case studies. `backend/requirements-verified.txt` pins the observed Windows Python 3.12 core environment; optional Neo4j/PostgreSQL drivers remain in the main requirements file. This snapshot is not a complete transitive lockfile.

```powershell
python -m pytest -q
cd frontend
npm test
npm run build
```

Backend tests cover invalid endpoints/provenance schemas, exact resolution, label exclusion, split isolation, training/checkpoint restoration, mocked source response/cache handling, and the complete API/database/agent workflow. Frontend tests cover search, empty evidence state and API errors. They do not replace browser visual QA. Optional integration tests run only with `TEST_NEO4J_URI` / `NEO4J_PASSWORD` and `TEST_POSTGRES_URL` pointing to dedicated test databases.

## References and evidence policy

No biomedical findings or experimental citations are bundled. Technical source references include [Europe PMC API](https://europepmc.org/RestfulWebService), [ChEMBL web services](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services), [Open Targets GraphQL documentation](https://github.com/opentargets/platform-docs/blob/main/data-access/graphql-api.md), [PyTorch](https://pytorch.org/docs/stable/), [NetworkX](https://networkx.org/documentation/stable/), and [FastAPI](https://fastapi.tiangolo.com/). Review upstream licenses before redistributing source records. Application code is MIT licensed; upstream content retains its own terms.
